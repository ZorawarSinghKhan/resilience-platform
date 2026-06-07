import requests as req_lib
from flask import Flask, render_template, request, jsonify, redirect, url_for, send_file, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
from models import db, User, TestRun
from services.deployer import deploy_image, wait_for_pods, cleanup_deployment
from services.chaos_runner import run_all_chaos_tests
from services.scorer import calculate_scores
from services.report_generator import generate_report
from dotenv import load_dotenv
import threading, uuid, time, os, requests as req_lib

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'resilience-secret-key-change-in-prod')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///resilience.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', '')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', '')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_USERNAME', '')

db.init_app(app)
mail = Mail(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

jobs = {}

def send_notifications(notify_email, slack_url, docker_images, all_results):
    summary_lines = []
    for r in all_results:
        if r.get('scores'):
            line = f"{r['docker_image']} - Grade {r['scores']['grade']} ({r['scores']['overall']}/100)"
        else:
            line = f"{r['docker_image']} - FAILED to deploy"
        summary_lines.append(line)
    summary = '\n'.join(summary_lines)

    if notify_email:
        try:
            with app.app_context():
                msg = Message(
                    subject='Resilience Test Complete',
                    recipients=[notify_email],
                    body=f"Your resilience test finished.\n\n{summary}\n\nLog in to download PDF reports."
                )
                mail.send(msg)
        except Exception as e:
            print(f'[Email Error] {e}')

def run_test_job(job_id, docker_images, user_id, notify_email=None, slack_url=None):
    all_results = []
    total = len(docker_images)

    for idx, image in enumerate(docker_images):
        jobs[job_id]['status'] = 'deploying'
        jobs[job_id]['message'] = f'[{idx+1}/{total}] Deploying {image}...'

        success, deploy_result = deploy_image(image)
        image_result = {
            'docker_image': image,
            'deployed': False,
            'pods_ready': False,
            'deploy_error': None,
            'test_results': None,
            'scores': None,
            'report_path': None
        }

        if not success:
            image_result['deploy_error'] = deploy_result
            all_results.append(image_result)
            continue

        image_result['deployed'] = True
        safe_name = deploy_result

        jobs[job_id]['status'] = 'waiting'
        jobs[job_id]['message'] = f'[{idx+1}/{total}] Waiting for {image} pods...'

        pods_ready = wait_for_pods(safe_name)
        if not pods_ready:
            cleanup_deployment(safe_name)
            all_results.append(image_result)
            continue

        image_result['pods_ready'] = True

        for i, test_name in enumerate(['Pod Chaos', 'CPU Stress', 'Memory Stress',
                                        'Network Delay', 'Packet Loss', 'Recovery']):
            jobs[job_id]['status'] = 'testing'
            jobs[job_id]['message'] = f'[{idx+1}/{total}] {image} - {test_name} ({i+1}/6)'
            time.sleep(1)

        test_results = run_all_chaos_tests(safe_name)
        scores = calculate_scores(test_results)
        report_path = generate_report(f'{job_id}-{idx}', image, test_results, scores)

        image_result['test_results'] = test_results
        image_result['scores'] = scores
        image_result['report_path'] = report_path

        cleanup_deployment(safe_name)
        all_results.append(image_result)

    with app.app_context():
        run = TestRun(
            user_id=user_id,
            docker_images=', '.join(docker_images),
            overall_scores=', '.join(
                str(r['scores']['overall']) if r.get('scores') else 'N/A'
                for r in all_results
            ),
            grades=', '.join(
                r['scores']['grade'] if r.get('scores') else 'N/A'
                for r in all_results
            ),
        )
        db.session.add(run)
        db.session.commit()

    send_notifications(notify_email, slack_url, docker_images, all_results)

    jobs[job_id]['all_results'] = all_results
    jobs[job_id]['status'] = 'done'
    jobs[job_id]['message'] = 'All tests complete!'

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        if not username or not password:
            flash('Username and password required.')
            return render_template('register.html')
        if User.query.filter_by(username=username).first():
            flash('Username already taken.')
            return render_template('register.html')
        user = User(username=username, password=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        user = User.query.filter_by(username=username).first()
        if not user or not check_password_hash(user.password, password):
            flash('Invalid username or password.')
            return render_template('login.html')
        login_user(user)
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/history')
@login_required
def history():
    runs = TestRun.query.filter_by(user_id=current_user.id).order_by(TestRun.ran_at.desc()).all()
    return render_template('history.html', runs=runs, username=current_user.username)

@app.route('/')
@login_required
def index():
    return render_template('index.html', username=current_user.username)

@app.route('/run-test', methods=['POST'])
@login_required
def run_test():
    raw = request.form.get('docker_images', '')
    docker_images = [i.strip() for i in raw.split(',') if i.strip()]
    if not docker_images:
        return redirect(url_for('index'))

    notify_email = request.form.get('notify_email', '').strip() or None
    slack_url = None

    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        'status': 'starting',
        'message': 'Starting tests...',
        'docker_images': docker_images,
        'all_results': []
    }
    thread = threading.Thread(
        target=run_test_job,
        args=(job_id, docker_images, current_user.id, notify_email, slack_url)
    )
    thread.daemon = True
    thread.start()
    return redirect(url_for('loading', job_id=job_id))

@app.route('/loading/<job_id>')
@login_required
def loading(job_id):
    job = jobs.get(job_id)
    if not job:
        return redirect(url_for('index'))
    return render_template('loading.html', job_id=job_id,
                           docker_image=', '.join(job.get('docker_images', [])))

@app.route('/status/<job_id>')
def status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({'status': 'not_found'})
    return jsonify({'status': job['status'], 'message': job['message']})

@app.route('/result/<job_id>')
@login_required
def result(job_id):
    job = jobs.get(job_id)
    if not job or job['status'] != 'done':
        return redirect(url_for('loading', job_id=job_id))
    return render_template('result.html', all_results=job['all_results'],
                           job_id=job_id, username=current_user.username)

@app.route('/download/<job_id>/<int:image_index>')
@login_required
def download(job_id, image_index):
    job = jobs.get(job_id)
    if not job:
        return redirect(url_for('index'))
    try:
        image_result = job['all_results'][image_index]
        report_path = image_result.get('report_path')
        if not report_path:
            return redirect(url_for('index'))
        safe_image = image_result['docker_image'].replace(':', '-').replace('/', '-')
        return send_file(report_path, as_attachment=True,
                         download_name=f'resilience-report-{safe_image}.pdf')
    except (IndexError, KeyError):
        return redirect(url_for('index'))

@app.route('/monitoring')
@login_required
def monitoring():
    return render_template('monitoring.html', username=current_user.username)

@app.route('/grafana-proxy/<path:subpath>', methods=['GET','POST'])
@login_required  
def grafana_proxy(subpath):
    grafana_url = 'http://prometheus-grafana.monitoring.svc.cluster.local:80'
    url = f"{grafana_url}/{subpath}"
    params = request.query_string.decode()
    if params:
        url = f"{url}?{params}"
    try:
        resp = req_lib.get(url, timeout=10,
                           headers={'X-WEBAUTH-USER': 'admin'},
                           allow_redirects=True)
        excluded = ['content-encoding','content-length','transfer-encoding','connection']
        headers = {k:v for k,v in resp.headers.items() if k.lower() not in excluded}
        return resp.content, resp.status_code, headers
    except Exception as e:
        return f"Grafana unavailable: {e}", 503

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=False, port=5001, host="0.0.0.0")
