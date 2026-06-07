import subprocess
import time
import yaml
import os


def generate_pod_chaos(safe_name, namespace="chaos-testing"):
    return {
        "apiVersion": "chaos-mesh.org/v1alpha1",
        "kind": "PodChaos",
        "metadata": {"name": f"pod-chaos-{safe_name}", "namespace": namespace},
        "spec": {
            "action": "pod-kill",
            "mode": "one",
            "selector": {
                "namespaces": ["default"],
                "labelSelectors": {"app": f"resilience-{safe_name}"}
            },
            "duration": "30s"
        }
    }


def generate_cpu_stress(safe_name, namespace="chaos-testing"):
    return {
        "apiVersion": "chaos-mesh.org/v1alpha1",
        "kind": "StressChaos",
        "metadata": {"name": f"cpu-stress-{safe_name}", "namespace": namespace},
        "spec": {
            "mode": "one",
            "selector": {
                "namespaces": ["default"],
                "labelSelectors": {"app": f"resilience-{safe_name}"}
            },
            "stressors": {"cpu": {"workers": 2, "load": 80}},
            "duration": "60s"
        }
    }


def generate_memory_stress(safe_name, namespace="chaos-testing"):
    return {
        "apiVersion": "chaos-mesh.org/v1alpha1",
        "kind": "StressChaos",
        "metadata": {"name": f"memory-stress-{safe_name}", "namespace": namespace},
        "spec": {
            "mode": "one",
            "selector": {
                "namespaces": ["default"],
                "labelSelectors": {"app": f"resilience-{safe_name}"}
            },
            "stressors": {"memory": {"workers": 2, "size": "256MB"}},
            "duration": "60s"
        }
    }


def generate_network_delay(safe_name, namespace="chaos-testing"):
    return {
        "apiVersion": "chaos-mesh.org/v1alpha1",
        "kind": "NetworkChaos",
        "metadata": {"name": f"network-delay-{safe_name}", "namespace": namespace},
        "spec": {
            "action": "delay",
            "mode": "all",
            "selector": {
                "namespaces": ["default"],
                "labelSelectors": {"app": f"resilience-{safe_name}"}
            },
            "delay": {"latency": "3000ms", "correlation": "100", "jitter": "0ms"},
            "duration": "60s"
        }
    }


def generate_packet_loss(safe_name, namespace="chaos-testing"):
    return {
        "apiVersion": "chaos-mesh.org/v1alpha1",
        "kind": "NetworkChaos",
        "metadata": {"name": f"packet-loss-{safe_name}", "namespace": namespace},
        "spec": {
            "action": "loss",
            "mode": "one",
            "selector": {
                "namespaces": ["default"],
                "labelSelectors": {"app": f"resilience-{safe_name}"}
            },
            "loss": {"loss": "30"},
            "duration": "60s"
        }
    }


def apply_chaos(chaos_dict, yaml_path):
    with open(yaml_path, "w") as f:
        yaml.dump(chaos_dict, f)
    result = subprocess.run(
        ["kubectl", "apply", "-f", yaml_path],
        capture_output=True, text=True
    )
    return result.returncode == 0


def delete_chaos(yaml_path):
    subprocess.run(
        ["kubectl", "delete", "-f", yaml_path, "--ignore-not-found=true"],
        capture_output=True
    )


def get_pod_metrics(safe_name):
    result = subprocess.run(
        ["kubectl", "top", "pods", "-l", f"app=resilience-{safe_name}", "--no-headers"],
        capture_output=True, text=True
    )
    cpu_values = []
    mem_values = []
    for line in result.stdout.strip().split("\n"):
        if line:
            parts = line.split()
            if len(parts) >= 3:
                cpu = parts[1].replace('m', '')
                mem = parts[2].replace('Mi', '').replace('Gi', '000')
                if cpu.isdigit():
                    cpu_values.append(int(cpu))
                if mem.isdigit():
                    mem_values.append(int(mem))
    return {
        "cpu_millicores": max(cpu_values) if cpu_values else 0,
        "memory_mb": max(mem_values) if mem_values else 0
    }


def check_recovery(safe_name, required_pods=2):
    start = time.perf_counter()
    time.sleep(5)

    peak_cpu = 0
    peak_mem = 0

    for _ in range(25):
        metrics = get_pod_metrics(safe_name)
        peak_cpu = max(peak_cpu, metrics['cpu_millicores'])
        peak_mem = max(peak_mem, metrics['memory_mb'])

        result = subprocess.run(
            ["kubectl", "get", "pods", "-l", f"app=resilience-{safe_name}", "--no-headers"],
            capture_output=True, text=True
        )
        running = len([
            l for l in result.stdout.strip().split("\n")
            if l and "Running" in l
        ])

        if running >= required_pods:
            recovery_time_ms = round((time.perf_counter() - start) * 1000)

            restart_result = subprocess.run(
                ["kubectl", "get", "pods", "-l", f"app=resilience-{safe_name}",
                 "-o", "jsonpath={.items[*].status.containerStatuses[*].restartCount}"],
                capture_output=True, text=True
            )
            restart_count = sum(
                int(x) for x in restart_result.stdout.split() if x.isdigit()
            )

            deployment_health = max(50, min(100,
                100 - (recovery_time_ms / 1000) * 1.5 - (restart_count * 5)
            ))

            return {
                "status": "PASS",
                "recovery_time_ms": recovery_time_ms,
                "recovery_time": round(recovery_time_ms / 1000, 2),
                "running_pods": running,
                "restart_count": restart_count,
                "deployment_health": round(deployment_health),
                "peak_cpu_millicores": peak_cpu,
                "peak_memory_mb": peak_mem
            }

        time.sleep(2)

    return {
        "status": "FAIL",
        "recovery_time_ms": 0,
        "recovery_time": 0,
        "running_pods": 0,
        "restart_count": 0,
        "deployment_health": 0,
        "peak_cpu_millicores": 0,
        "peak_memory_mb": 0
    }


def run_all_chaos_tests(safe_name):
    results = {}

    tests = [
        {
            "name": "Pod Chaos Test",
            "key": "pod_chaos",
            "yaml_func": generate_pod_chaos,
            "path": f"/tmp/pod-chaos-{safe_name}.yaml"
        },
        {
            "name": "CPU Stress Test",
            "key": "cpu_stress",
            "yaml_func": generate_cpu_stress,
            "path": f"/tmp/cpu-stress-{safe_name}.yaml"
        },
        {
            "name": "Memory Stress Test",
            "key": "memory_stress",
            "yaml_func": generate_memory_stress,
            "path": f"/tmp/memory-stress-{safe_name}.yaml"
        },
        {
            "name": "Network Delay Test",
            "key": "network_delay",
            "yaml_func": generate_network_delay,
            "path": f"/tmp/network-delay-{safe_name}.yaml"
        },
        {
            "name": "Packet Loss Test",
            "key": "packet_loss",
            "yaml_func": generate_packet_loss,
            "path": f"/tmp/packet-loss-{safe_name}.yaml"
        },
    ]

    for test in tests:
        print(f"\nRunning: {test['name']}")
        chaos_dict = test["yaml_func"](safe_name)
        applied = apply_chaos(chaos_dict, test["path"])

        if not applied:
            results[test["key"]] = {
                "status": "FAIL",
                "recovery_time_ms": 0,
                "recovery_time": 0,
                "running_pods": 0,
                "restart_count": 0,
                "deployment_health": 0,
                "peak_cpu_millicores": 0,
                "peak_memory_mb": 0
            }
            continue

        recovered = check_recovery(safe_name)
        results[test["key"]] = recovered
        print(f"Recovery: {recovered}")
        delete_chaos(test["path"])
        time.sleep(10)

    print("\nRunning: Recovery Validation")
    final = check_recovery(safe_name)
    results["recovery_validation"] = final
    print(f"Final: {final}")

    return results
