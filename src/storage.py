import os
import re
import boto3
from datetime import datetime
from pathlib import Path


class Storage:
    def __init__(self):
        self.s3 = boto3.resource("s3")

    def upload_file(self, bucket, path):
        print(f"Uploading {path}...\n")
        filename = os.path.basename(path)
        dir_tree = os.path.dirname(path)
        parent_folder = os.path.basename(dir_tree)
        self.s3.Bucket(bucket).upload_file(path, os.path.join(parent_folder, filename))
        print("Upload completed!")

    def create_next_session_folder(self):
        sessions_path = os.path.join(Path(__file__).resolve().parent.parent, "sessions")
        curr_sess_path = os.path.join(sessions_path, f"sess_{datetime.now().strftime('%d_%m_%Y__%H_%M_%S')}")
        os.makedirs(curr_sess_path, exist_ok=True)

        return curr_sess_path

    def create_next_train_folder(self):
        recordings_path = os.path.join(Path(__file__).resolve().parent.parent, "recordings")

        # List subfolders in recordings folder or create it in case it does not exist
        try:
            folder_names = [f.name for f in os.scandir(recordings_path) if f.is_dir()]
        except FileNotFoundError:
            folder_names = []
            os.makedirs(recordings_path)
            next_folder = os.path.join(recordings_path, "1")

        # Nauturally sort folder names
        def sorted_alphanumeric(data):
            convert = lambda text: int(text) if text.isdigit() else text.lower()
            alphanum_key = lambda key: [convert(c) for c in re.split('([0-9]+)', key)]
            return sorted(data, key=alphanum_key)
        folder_names = sorted_alphanumeric(folder_names)

        # Check if there are any folders in recordings and initialize a folder with number 1 if not
        try:
            next_folder = os.path.join(recordings_path, folder_names[-1])
        except IndexError:
            next_folder = os.path.join(recordings_path, "1")
            os.makedirs(next_folder)

        # Check if last folder contains any items and create new folder if it does
        if len(os.listdir(next_folder)) != 0:
            next_folder = os.path.join(recordings_path, str(int(folder_names[-1]) + 1))
            os.makedirs(next_folder)

        return next_folder
