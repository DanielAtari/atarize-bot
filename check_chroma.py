from chromadb import PersistentClient
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

client = PersistentClient(path="./chroma_db")  # או הנתיב שבו אתה שומר את הדאטה
collection = client.get_or_create_collection(name="atarize_knowledge")
print("Total documents in collection:", collection.count())
