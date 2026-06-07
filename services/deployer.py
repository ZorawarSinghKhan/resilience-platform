import subprocess
import time
import yaml
import os

def generate_deployment_yaml(image_name):
    # Create a safe name from the image (e.g. nginx:latest -> nginx-latest)
    safe_name = image_name.replace(":", "-").replace("/", "-").replace(".", "-")

    deployment = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": f"resilience-{safe_name}",
            "namespace": "default"
        },
        "spec": {
            "replicas": 2,
            "selector": {
                "matchLabels": {
                    "app": f"resilience-{safe_name}"
                }
            },
            "template": {
                "metadata": {
                    "labels": {
                        "app": f"resilience-{safe_name}"
                    }
                },
                "spec": {
                    "containers": [{
                        "name": "app",
                        "image": image_name
                    }]
                }
            }
        }
    }
    return deployment, safe_name


def deploy_image(image_name):
    deployment, safe_name = generate_deployment_yaml(image_name)

    # Save YAML to a temp file
    yaml_path = f"/tmp/resilience-{safe_name}.yaml"
    with open(yaml_path, "w") as f:
        yaml.dump(deployment, f)

    # Apply it to Kubernetes
    result = subprocess.run(
        ["kubectl", "apply", "-f", yaml_path],
        capture_output=True, text=True
    )

    if result.returncode != 0:
        return False, result.stderr

    return True, safe_name


def wait_for_pods(safe_name, timeout=60):
    print(f"Waiting for pods: resilience-{safe_name}")

    for i in range(timeout):
        result = subprocess.run(
            [
                "kubectl", "get", "pods",
                "-l", f"app=resilience-{safe_name}",
                "--field-selector=status.phase=Running",
                "--no-headers"
            ],
            capture_output=True, text=True
        )

        running = len([
            line for line in result.stdout.strip().split("\n")
            if line and "Running" in line
        ])

        print(f"  Running pods: {running}")

        if running >= 2:
            return True

        time.sleep(2)

    return False


def cleanup_deployment(safe_name):
    subprocess.run(
        ["kubectl", "delete", "deployment", f"resilience-{safe_name}",
         "--ignore-not-found=true"],
        capture_output=True
    )
