import sys
print("Python executable:", sys.executable)
print("Python version:", sys.version)
print("")

try:
    import pydub
    print("✅ pydub found at:", pydub.__file__)
except ImportError as e:
    print("❌ pydub import failed:", e)

print("")
print("sys.path:")
for p in sys.path:
    print("  ", p)