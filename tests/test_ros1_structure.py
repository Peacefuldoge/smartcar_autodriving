from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def test_package_and_launch_xml_are_well_formed():
    ET.parse(ROOT / "package.xml")
    for path in (ROOT / "launch").glob("*.launch"):
        ET.parse(path)


def test_required_ros1_files_exist():
    required = [
        "CMakeLists.txt",
        "package.xml",
        "setup.py",
        "msg/DriveCommand.msg",
        "msg/Detection.msg",
        "msg/DetectionArray.msg",
        "launch/autonomous.launch",
        "launch/manual.launch",
        "config/ros1.yaml",
    ]
    for item in required:
        assert (ROOT / item).is_file(), item


def test_all_installed_ros_nodes_have_shebang():
    for path in (ROOT / "ros_nodes").glob("*.py"):
        assert path.read_text(encoding="utf-8").startswith("#!/usr/bin/env python3")
