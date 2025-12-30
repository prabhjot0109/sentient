import pkgutil
import langchain


def find_submodules(package):
    return [name for _, name, _ in pkgutil.iter_modules(package.__path__)]


print("Langchain submodules:", find_submodules(langchain))

try:
    from langchain.chains import create_retrieval_chain

    print("Success: from langchain.chains import create_retrieval_chain")
except ImportError as e:
    print("Failed: from langchain.chains import create_retrieval_chain -", e)

# Search in community
try:
    import langchain_community

    print(
        "Langchain Community submodules:",
        [name for _, name, _ in pkgutil.iter_modules(langchain_community.__path__)],
    )
except ImportError:
    print("langchain_community not found")
