try:
    from langchain_community.chains import create_retrieval_chain

    print("Success: from langchain_community.chains import create_retrieval_chain")
except ImportError:
    print("Failed: from langchain_community.chains import create_retrieval_chain")

try:
    from langchain.chains import create_retrieval_chain

    print("Success: from langchain.chains import create_retrieval_chain")
except ImportError:
    print("Failed: from langchain.chains import create_retrieval_chain")
