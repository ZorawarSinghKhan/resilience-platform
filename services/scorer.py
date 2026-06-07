def calculate_scores(test_results):
    scores = {}

    def performance_score(result):
        if result is None or result == 'FAIL':
            return 0
        if isinstance(result, dict) and result.get('status') == 'FAIL':
            return 0
        if not isinstance(result, dict):
            return 0

        recovery_time = result.get('recovery_time', 999)
        restart_count = result.get('restart_count', 0)
        deployment_health = result.get('deployment_health', 50)
        peak_cpu = result.get('peak_cpu_millicores', 0)
        peak_mem = result.get('peak_memory_mb', 0)

        # Recovery time score (40%) — banded with 5-point classes
        if recovery_time <= 5:
            time_score = 100 - (recovery_time / 5) * 5
        elif recovery_time <= 10:
            time_score = 94 - ((recovery_time - 5) / 5) * 9
        elif recovery_time <= 15:
            time_score = 84 - ((recovery_time - 10) / 5) * 9
        elif recovery_time <= 20:
            time_score = 74 - ((recovery_time - 15) / 5) * 9
        elif recovery_time <= 25:
            time_score = 64 - ((recovery_time - 20) / 5) * 9
        elif recovery_time <= 30:
            time_score = 54 - ((recovery_time - 25) / 5) * 9
        elif recovery_time <= 40:
            time_score = 44 - ((recovery_time - 30) / 10) * 9
        elif recovery_time <= 50:
            time_score = 34 - ((recovery_time - 40) / 10) * 14
        else:
            time_score = max(10, 19 - ((recovery_time - 50) / 10) * 9)

        # CPU score (20%) — lower peak CPU = better
        if peak_cpu <= 200:
            cpu_score = 100 - (peak_cpu / 200) * 10
        elif peak_cpu <= 500:
            cpu_score = 89 - ((peak_cpu - 200) / 300) * 19
        elif peak_cpu <= 800:
            cpu_score = 69 - ((peak_cpu - 500) / 300) * 19
        else:
            cpu_score = max(20, 49 - ((peak_cpu - 800) / 200) * 29)

        # Memory score (20%) — lower peak memory = better
        if peak_mem <= 100:
            mem_score = 100 - (peak_mem / 100) * 10
        elif peak_mem <= 300:
            mem_score = 89 - ((peak_mem - 100) / 200) * 19
        elif peak_mem <= 600:
            mem_score = 69 - ((peak_mem - 300) / 300) * 19
        else:
            mem_score = max(20, 49 - ((peak_mem - 600) / 200) * 29)

        # Restart penalty (10%)
        restart_score = max(0, 100 - (restart_count * 15))

        # Deployment health (10%)
        health_score = deployment_health

        final = (
            time_score * 0.40 +
            cpu_score * 0.20 +
            mem_score * 0.20 +
            restart_score * 0.10 +
            health_score * 0.10
        )

        return round(min(100, max(0, final)))

    scores['self_healing'] = performance_score(test_results.get('pod_chaos'))
    scores['cpu_resilience'] = performance_score(test_results.get('cpu_stress'))
    scores['memory_resilience'] = performance_score(test_results.get('memory_stress'))
    scores['network_resilience'] = performance_score(test_results.get('network_delay'))
    scores['packet_resilience'] = performance_score(test_results.get('packet_loss'))
    scores['recovery'] = performance_score(test_results.get('recovery_validation'))

    weights = {
        'self_healing': 0.25,
        'cpu_resilience': 0.15,
        'memory_resilience': 0.15,
        'network_resilience': 0.15,
        'packet_resilience': 0.15,
        'recovery': 0.15
    }

    scores['overall'] = round(sum(scores[k] * weights[k] for k in weights))

    if scores['overall'] >= 90:
        scores['grade'] = 'A+'
        scores['grade_label'] = 'Exceptional'
        scores['grade_color'] = '#00ff88'
    elif scores['overall'] >= 80:
        scores['grade'] = 'A'
        scores['grade_label'] = 'Excellent'
        scores['grade_color'] = '#00dd77'
    elif scores['overall'] >= 70:
        scores['grade'] = 'B'
        scores['grade_label'] = 'Good'
        scores['grade_color'] = '#88ff00'
    elif scores['overall'] >= 60:
        scores['grade'] = 'C'
        scores['grade_label'] = 'Average'
        scores['grade_color'] = '#ffaa00'
    elif scores['overall'] >= 45:
        scores['grade'] = 'D'
        scores['grade_label'] = 'Below Average'
        scores['grade_color'] = '#ff6600'
    else:
        scores['grade'] = 'F'
        scores['grade_label'] = 'Poor'
        scores['grade_color'] = '#ff4444'

    return scores
