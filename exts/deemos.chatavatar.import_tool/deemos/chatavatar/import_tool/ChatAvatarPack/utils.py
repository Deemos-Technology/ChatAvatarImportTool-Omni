import os
import zipfile
import random
import string
from os import PathLike
from typing import Iterable

def generate_safe_name_from_basename(basename: str) -> str:
    if basename.endswith(".zip"):
        basename = basename[:-4]
    basename = basename.replace(" ", "_")
    return basename

def file_checker(check_list: Iterable[Iterable[PathLike]]):
    """For all iterables in check_list, check if any file in the inner iterable exists.

    Args:
        check_list (Iterable[Iterable[PathLike]]): Checking rule
    """
    def check(fps: Iterable[PathLike]):
        fps_set = set(fps)
        return all(
            (
                any(
                    check_fp in fps_set for check_fp in check_element
                ) for check_element in check_list
            )
        )
    return check

def safe_extractall(zip_file: zipfile.ZipFile, initial_unzip_path: str) -> str:
    def random_folder_name(length=8):
        letters = string.ascii_lowercase
        return ''.join(random.choice(letters) for i in range(length))

    # 如果initial_unzip_path不存在，直接在该路径下创建文件夹并解压
    if not os.path.exists(initial_unzip_path):
        os.makedirs(initial_unzip_path)
        zip_file.extractall(initial_unzip_path)
        return initial_unzip_path

    # 如果initial_unzip_path存在
    conflict = False
    for file in zip_file.namelist():
        full_path = os.path.join(initial_unzip_path, file)
        if os.path.exists(full_path):
            # 检查同名的文件夹或文件是否存在
            if (file.endswith('/') and not os.path.isdir(full_path)) or \
               (not file.endswith('/') and not os.path.isfile(full_path)):
                conflict = True
                break

    if conflict:
        # 存在冲突，创建新的随机文件夹
        random_length = 8
        new_path = os.path.join(initial_unzip_path, random_folder_name(random_length))
        current_length_attempts = 1
        while os.path.exists(new_path):
            if current_length_attempts >= 100:
                random_length += 1
                current_length_attempts = 0
            new_path = os.path.join(initial_unzip_path, random_folder_name(random_length))
            current_length_attempts += 1
        os.makedirs(new_path)
        zip_file.extractall(new_path)
        return new_path
    else:
        # 没有冲突，只解压不存在的文件
        for file in zip_file.namelist():
            full_path = os.path.join(initial_unzip_path, file)
            if not os.path.exists(full_path):
                zip_file.extract(file, initial_unzip_path)
        return initial_unzip_path
