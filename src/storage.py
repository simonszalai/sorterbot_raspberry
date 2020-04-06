"""
Handles uploads to AWS s3 and creation of local folder for files to be saved.

"""

import os
import re
import boto3
from datetime import datetime
from pathlib import Path


class Storage:
    def __init__(self):
        """
        Includes methods for upload to s3 and creation of folders.
        """
        self.s3 = boto3.resource("s3")

    def upload_file(self, bucket, path):
        """
        Uploads a file to s3.

        Parameters
        ----------
        bucket : str
            Bucket name on AWS s3.
        path : str
            Path of the file to be uploaded.

        """

        filename = os.path.basename(path)
        print(f"Uploading {filename}...")
        dir_tree = os.path.dirname(path)
        parent_folder = os.path.basename(dir_tree)
        self.s3.Bucket(bucket).upload_file(path, os.path.join(parent_folder, filename))
        print(f"Upload of {filename} completed!")

    def create_next_session_folder(self):
        """
        Creates a folder for the inference images names sess_{datetime}.

        Returns
        -------
        curr_sess_path : str
            Absolute path of the current session folder.

        """

        sessions_path = os.path.join(Path(__file__).resolve().parent.parent, "sessions")
        curr_sess_path = os.path.join(sessions_path, f"sess_{datetime.now().strftime('%d_%m_%Y__%H_%M_%S')}")
        os.makedirs(curr_sess_path, exist_ok=True)

        return curr_sess_path

    def create_next_train_folder(self):
        """
        Creates a folder for the training videos, named as simple integers starting from 1.
        It will find the highest existing number and increment it to get the current folder name.
        If the highest number is an empty folder, that will be used instead of creating a new one.

        Returns
        -------
        next_folder : str
            Absolute path of the next folder for training videos.

        """

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
