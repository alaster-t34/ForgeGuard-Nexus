from forgeguard_edge.platform import PlatformReport, build_preflight_checks, parse_nv_tegra_release


def test_parse_nv_tegra_release():
    release, revision = parse_nv_tegra_release(
        "# R39 (release), REVISION: 2.0, GCID: 12345, BOARD: generic, EABI: aarch64"
    )
    assert release == "39"
    assert revision == "2.0"


def test_preflight_requires_current_jetson_stack():
    report = PlatformReport(
        hostname="jetson",
        architecture="aarch64",
        kernel="6.8",
        operating_system="Linux",
        python_version="3.12",
        device_model="NVIDIA Jetson AGX Orin Developer Kit",
        is_jetson=True,
        l4t_release="39",
        l4t_revision="2.0",
        cuda_version="13.2",
        tensorrt_version="10.16.2",
        docker_version="28.0",
        nvidia_runtime_configured=True,
        gpu_device_nodes=["/dev/nvhost-gpu"],
    )
    checks = build_preflight_checks(report)
    required = {item.name: item.ok for item in checks if item.required}
    assert all(required.values())


def test_preflight_rejects_non_jetson_host():
    report = PlatformReport(
        hostname="host",
        architecture="x86_64",
        kernel="6.8",
        operating_system="Linux",
        python_version="3.13",
        device_model=None,
        is_jetson=False,
        l4t_release=None,
        l4t_revision=None,
        cuda_version=None,
        tensorrt_version=None,
        docker_version=None,
        nvidia_runtime_configured=False,
    )
    checks = build_preflight_checks(report)
    assert any(item.required and not item.ok for item in checks)
