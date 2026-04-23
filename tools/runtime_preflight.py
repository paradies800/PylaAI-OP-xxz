import platform
import sys


VC_REDIST_URL = "https://aka.ms/vs/17/release/vc_redist.x64.exe"


def print_header():
    print("=" * 58)
    print("PylaAI startup check")
    print("=" * 58)


def check_python():
    if sys.version_info[:2] != (3, 11) or platform.architecture()[0] != "64bit":
        print_header()
        print("Python 3.11 64-bit is required.")
        print(f"Current Python: {sys.version.split()[0]} {platform.architecture()[0]}")
        print("Run setup.exe again, or install Python 3.11 x64.")
        return False
    return True


def check_onnxruntime():
    try:
        import onnxruntime  # noqa: F401
        return True
    except Exception as exc:
        message = str(exc)
        print_header()
        print("ONNX Runtime could not start.")
        print("")
        if "onnxruntime_pybind11_state" in message or "DLL load failed" in message:
            print("Windows is missing a native runtime DLL, or the ONNX package is damaged.")
            print("")
            print("The launcher will try to repair the Python packages now.")
            print("If it still fails after repair, install this Microsoft runtime:")
            print(f"  {VC_REDIST_URL}")
            print("")
            print("After installing it, restart Windows and run PylaAI again.")
        else:
            print("The ONNX package import failed with this error:")
            print(f"  {message}")
            print("")
            print("The launcher will try to repair the Python packages now.")
        return False


def main():
    if not check_python():
        return 1
    if not check_onnxruntime():
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
