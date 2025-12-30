import sys
import importlib.util

print("Python Executable:", sys.executable)
print("Sys Path:", sys.path)

try:
    import langchain

    print("Langchain found:", langchain.__file__)
    print("Langchain version:", langchain.__version__)
except ImportError as e:
    print("Langchain import failed:", e)

try:
    import langchain.chains

    print("langchain.chains found")
except ImportError as e:
    print("langchain.chains import failed:", e)

try:
    from langchain.chains import create_retrieval_chain

    print("create_retrieval_chain found")
except ImportError as e:
    print("create_retrieval_chain import failed:", e)
