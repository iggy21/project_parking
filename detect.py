import cv2
import pytesseract
from PyQt5.QtGui import QPixmap

pytesseract.pytesseract.tesseract_cmd = r'D:/Program Files/tesseract.exe'

def detect_license_plate(image_path):
    """Funkcja wykrywania tablic rejestracyjnych z obrazu."""
    try:
        img = cv2.imread(image_path, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Obraz nie został wczytany poprawnie")

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        edged = cv2.Canny(binary, 170, 200)
        cnts, _ = cv2.findContours(edged.copy(), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        cnts = sorted(cnts, key=cv2.contourArea, reverse=True)[:30]

        for c in cnts:
            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.02 * peri, True)
            if len(approx) == 4:
                x, y, w, h = cv2.boundingRect(approx)
                roi = binary[y:y + h, x:x + w]
                config = '-l eng --oem 3 --psm 6'
                text = pytesseract.image_to_string(roi, config=config).strip()
                if text:
                    return text

        return None
    except Exception as e:
        return str(e)
