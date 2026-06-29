import time
import cv2

from frame_source.base_frame_source import BaseFrameSource
from models.frame import Frame


class WebcamSource(BaseFrameSource):
    """
    Real-time webcam frame generator.
    Compatible with Frame-based pipeline architecture.
    """

    def __init__(self, camera_index: int = 0) -> None:
        self.camera_index = camera_index
        self.cap = cv2.VideoCapture(self.camera_index)

        if not self.cap.isOpened():
            raise RuntimeError(
                f"Cannot open webcam with index {self.camera_index}"
            )
        
        self.frame_id = 0
        

    def read(self) -> Frame | None:
        success, frame = self.cap.read()

        if not success or frame is None:
            raise RuntimeError("Failed to read frame from webcam")

        result = Frame(
            image=frame,
            timestamp=time.time(),
            frame_id=self.frame_id,
            source=f"wecam:{self.camera_index}"
        )
        
        self.frame_id += 1
        return result

    def release(self) -> None:
        """
        Release webcam resources.
        """

        if self.cap is not None:
            self.cap.release()
