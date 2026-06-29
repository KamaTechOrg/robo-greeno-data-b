from pathlib import Path
import time

import cv2
import numpy as np

from frame_source.base_frame_source import BaseFrameSource
from models.frame import Frame

class FolderSource(BaseFrameSource):
    """
    Reads images from a folder sequentially.
    """
    
    SUPPORTED_EXTENSIONS = {
        ".jpg",
        ".jpeg",
        ".png",
        ".bmp",
        ".webp"
    }

    def __init__(self, folder_path: str) -> None:
        self.folder_path = Path(folder_path)
        self.image_paths = sorted(
            path
            for path in self.folder_path.iterdir()
            if path.suffix.lower() in self.SUPPORTED_EXTENSIONS
        )
        self.current_index = 0
        

    def read(self) -> np.ndarray:
        if self.current_index >= len(self.image_paths):
           return None
       
        image_path = self.image_paths[self.current_index]
        image = cv2.imread(str(image_path))
       
        if image is None:
           raise FileNotFoundError(
               f"Failed to read image: {image_path}"
           )
           
        frame = Frame(
            image=image,
            timestamp=time.time(),
            frame_id=self.current_index,
            source=str(image_path)
        )
        self.current_index += 1
        return frame

    def release(self) -> None:
        pass
    
    def reset(self) -> None:
        self.current_index = 0