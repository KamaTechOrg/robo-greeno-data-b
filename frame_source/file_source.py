from pathlib import Path
import time

import cv2
import numpy as np

from frame_source.base_frame_source import BaseFrameSource
from models.frame import Frame

class FileSource(BaseFrameSource):
    """
    Single image source.

    Loads one image and returns it as a frame.
    After the image is returned once, read()
    returns None.
    """

    def __init__(self, image_path: str) -> None:
        self.image_path = Path(image_path)
        self._frame_sent = False

    def read(self) -> np.ndarray:
        if self._frame_sent:
           return None
       
        image = cv2.imread(str(self.image_path))
       
        if image is None:
           raise FileNotFoundError(
               f"Failed to load image: {self.image_path}"
           )
           
        self._frame_sent = True

        return Frame(
            image=image,
            timestamp=time.time(),
            frame_id=0,
            source="file"
        )

    def release(self) -> None:
        pass
    
    def reset(self) -> None:
        self._frame_sent = False