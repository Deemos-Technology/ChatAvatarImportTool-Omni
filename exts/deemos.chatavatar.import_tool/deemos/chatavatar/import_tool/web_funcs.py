from __future__ import annotations
from PySide6.QtWidgets import QMessageBox
import json
from ChatAvatarPack import defs as CADefs

from http.client import HTTPConnection, HTTPSConnection
from urllib.parse import urlparse

class HTTPConnectionContextManager:
    def __init__(self, host, port=None):
        self.conn = HTTPConnection(host, port)

    def __enter__(self):
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.conn.close()

class HTTPSConnectionContextManager:
    def __init__(self, host, port=None):
        self.conn = HTTPSConnection(host, port)

    def __enter__(self):
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.conn.close()

class WebFuncs:
    def __init__(self, url):
        parsed_result = urlparse(url)
        self.host = parsed_result.hostname
        self.port = parsed_result.port
        self.path = parsed_result.path
        self.scheme = parsed_result.scheme

    def import_pack(
        self,
        model_path: str,
        obj_name: str,
        texture_paths: dict[str, str],
        selected_pack: CADefs.PackInfo,
        selected_additional: CADefs.AdditionalElements,
        available_additional: CADefs.AdditionalElements,
        pack_name: str,
        additional_paths,
    ):
        ConnectionContextManager = {
            "http": HTTPConnectionContextManager,
            "https": HTTPSConnectionContextManager
        }[self.scheme]

        with ConnectionContextManager(self.host, self.port) as conn:
            data = json.dumps({
                "model_path": model_path,
                "obj_name": obj_name,
                "texture_paths": texture_paths,
                "selected_pack_resolution": selected_pack.resolution.value,
                "selected_pack_topology": selected_pack.topology.value,
                "selected_additional": selected_additional.value,
                "available_additional": available_additional.value,
                "pack_name": pack_name,
                "additional_paths": [
                    {
                        "part": key.value,
                        "value": value
                    }
                    for key, value in additional_paths.items()
                ]
            })
            headers = {'Content-type': 'application/json'}
            conn.request("POST", self.path + "/import", body=data, headers=headers)
            response = conn.getresponse()
            self.response = response
            return f"{response.status} ({response.reason}): {response.read().decode}"

    def pre_import(
        self,
        qwindow,
        model_path,
        obj_name,
        texture_paths,
        selected_pack,
        selected_additional,
        additional_elements,
        pack_name,
        additional_paths,
    ):
        pass

    def post_import(
        self,
        qwindow,
        model_path,
        obj_name,
        texture_paths,
        selected_pack,
        selected_additional,
        additional_elements,
        pack_name,
        additional_paths,
    ):
        # Prompt OK and allow closing window
        msg_box = QMessageBox(qwindow)
        msg_box.setWindowTitle("ChatAvatar Import Tool")
        if 200 <= self.response.status < 300:
            msg_box.setText(
                "Asset imported! You can now close the import tool window."
            )
        else:
            msg_box.setText(
                f"Asset import failed! ({self.response.status} {self.response.reason}: {self.response.read().decode})"
            )
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.exec()
