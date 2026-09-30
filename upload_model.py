from huggingface_hub import HfApi

api = HfApi()
api.create_repo(repo_id="akshat-02/contract-risk-classifier", repo_type="model")
api.upload_folder(
    folder_path="models/transformer_final",
    repo_id="akshat-02/contract-risk-classifier",
    repo_type="model"
)
print("Done.")