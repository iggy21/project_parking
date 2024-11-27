import mysql.connector
import datetime
import sys
import re
import time
import os
import numpy as np

from PyQt5 import QtCore, QtWidgets, uic, QtGui
from PyQt5.QtWidgets import QFileDialog
import cv2
import pytesseract

# Poprawiona ścieżka do Tesseract
pytesseract.pytesseract.tesseract_cmd = r'C:/Program Files/Tesseract-OCR/tesseract.exe'

# Połączenie z bazą danych
mydb = mysql.connector.connect(host="localhost", user="root", passwd="", database="car", autocommit=True)
mycursor = mydb.cursor()

try:
    # Tworzenie tabel, jeśli nie istnieją
    mycursor.execute("CREATE TABLE IF NOT EXISTS slot(carNumber VARCHAR(15), slot INT)")
    mycursor.execute("CREATE TABLE IF NOT EXISTS entry(carNumber VARCHAR(15), entry VARCHAR(40))")
    mycursor.execute("CREATE TABLE IF NOT EXISTS exits(carNumber VARCHAR(15), exit1 VARCHAR(40))")
    mycursor.execute("CREATE TABLE IF NOT EXISTS duration(carNumber VARCHAR(15), durationInSec INT)")
    mycursor.execute("CREATE TABLE IF NOT EXISTS cost(carNumber VARCHAR(15), cost INT)")

except mysql.connector.Error as err:
    print(f"Błąd podczas tworzenia tabel: {err}")

# Tablica przechowująca dostępność miejsc parkingowych
slots = [False for _ in range(5)]
car_numbers = [None for _ in range(5)]  # Przechowywanie numerów rejestracyjnych dla miejsc parkingowych


class Ui(QtWidgets.QMainWindow):
    def __init__(self):
        super(Ui, self).__init__()
        uic.loadUi("C:/Users/vene/Desktop/praca_parking/automatic_parking_system/front.ui", self)

        # Inicjalizacja elementów GUI
        self.ENTRYBUTTON = self.findChild(QtWidgets.QPushButton, 'ENTRYBUTTON')
        self.EXITBUTTON = self.findChild(QtWidgets.QPushButton, 'EXITBUTTON')
        self.loadImageButton = self.findChild(QtWidgets.QPushButton, 'loadImageButton')
        self.imagePreview = self.findChild(QtWidgets.QLabel, 'imagePreview')
        self.label_2 = self.findChild(QtWidgets.QLabel, 'label_2')
        self.comboBoxRejestracja = self.findChild(QtWidgets.QComboBox, 'comboBoxRejestracja')

        # Inicjalizacja przycisków miejsc parkingowych (5 miejsc)
        self.parking_buttons = []
        for i in range(1, 6):
            button = self.findChild(QtWidgets.QPushButton, f"s{i}")
            if button:
                self.parking_buttons.append(button)

        # Podłączenie przycisków do funkcji
        if self.ENTRYBUTTON is not None:
            self.ENTRYBUTTON.released.connect(self.handle_entry)
        else:
            print("Błąd: Nie znaleziono przycisku ENTRYBUTTON")

        if self.EXITBUTTON is not None:
            self.EXITBUTTON.released.connect(self.handle_exit)
        else:
            print("Błąd: Nie znaleziono przycisku EXITBUTTON")

        if self.loadImageButton is not None:
            self.loadImageButton.clicked.connect(self.load_image)
        else:
            print("Błąd: Nie znaleziono przycisku loadImageButton")

        if self.imagePreview is None:
            print("Błąd: Nie znaleziono pola do podglądu obrazu imagePreview")

        if self.label_2 is None:
            print("Błąd: Nie znaleziono etykiety label_2")

        if self.comboBoxRejestracja is None:
            print("Błąd: Nie znaleziono pola wyboru comboBoxRejestracja")

    def load_image(self):
        options = QFileDialog.Options()
        options |= QFileDialog.ReadOnly
        image_path, _ = QFileDialog.getOpenFileName(self, "Wybierz obraz", "", "Images (*.png *.jpg *.jpeg *.bmp)",
                                                    options=options)

        if image_path:
            pixmap = QtGui.QPixmap(image_path)
            self.imagePreview.setPixmap(pixmap.scaled(self.imagePreview.size(), QtCore.Qt.KeepAspectRatio))
            self.process_image(image_path)

    def process_image(self, image_path):
        try:
            img = cv2.imread(image_path, cv2.IMREAD_COLOR)
            if img is None:
                raise ValueError("Obraz nie został wczytany poprawnie")

            # Konwersja obrazu na skale szarości
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            # Zastosowanie progowania do uzyskania obrazu binarnego
            _, binary = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

            # Wykrywanie krawędzi
            edged = cv2.Canny(binary, 170, 200)

            # Znajdowanie konturów
            cnts, _ = cv2.findContours(edged.copy(), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
            cnts = sorted(cnts, key=cv2.contourArea, reverse=True)[:30]
            NumberPlateCnt = None

            # Szukanie konturu przypominającego tablicę rejestracyjną
            for c in cnts:
                peri = cv2.arcLength(c, True)
                approx = cv2.approxPolyDP(c, 0.02 * peri, True)
                if len(approx) == 4:
                    NumberPlateCnt = approx
                    break

            # Tworzenie maski i wyciąganie tablicy rejestracyjnej
            if NumberPlateCnt is not None:
                x, y, w, h = cv2.boundingRect(NumberPlateCnt)
                roi = binary[y:y + h, x:x + w]

                if roi.size == 0:
                    raise ValueError("Nie można wyciąć fragmentu obrazu z tablicą rejestracyjną")

                # Przekazanie obrazu do Tesseract OCR
                config = ('-l eng --oem 3 --psm 6')
                text = pytesseract.image_to_string(roi, config=config).strip()

                # Rejestracja numeru samochodu
                if text:
                    self.comboBoxRejestracja.addItem(text)
                    self.label_2.setText(f"Rozpoznano numer: {text}")
                else:
                    self.label_2.setText("Nie rozpoznano tablicy rejestracyjnej")
            else:
                self.label_2.setText("Nie znaleziono konturu przypominającego tablicę rejestracyjną")

        except Exception as e:
            self.label_2.setText(f"Błąd: {str(e)}")

    def handle_entry(self):
        rejestracja = self.comboBoxRejestracja.currentText().strip()
        if rejestracja:
            # Znalezienie pierwszego dostępnego miejsca
            try:
                slot_no = slots.index(False)
                slots[slot_no] = True
                car_numbers[slot_no] = rejestracja
                slot_no += 1

                # Zarejestrowanie czasu wjazdu
                entry_time = datetime.datetime.now()

                # Dodanie wpisów do bazy danych
                mycursor.execute("INSERT INTO slot (carNumber, slot) VALUES (%s, %s)", (rejestracja, slot_no))
                mycursor.execute("INSERT INTO entry (carNumber, entry) VALUES (%s, %s)", (rejestracja, entry_time))

                self.label_2.setText(f"Zarejestrowano wjazd dla: {rejestracja} (Miejsce: {slot_no})")

                # Aktualizacja przycisku miejsca parkingowego
                self.update_slot_buttons()
            except ValueError:
                self.label_2.setText("Brak dostępnych miejsc parkingowych")

    def handle_exit(self):
        rejestracja = self.comboBoxRejestracja.currentText().strip()
        if rejestracja:
            # Znalezienie numeru miejsca parkingowego
            mycursor.execute("SELECT slot FROM slot WHERE carNumber = %s", (rejestracja,))
            result = mycursor.fetchone()
            mycursor.fetchall()  # Odczytaj pozostałe wyniki, aby nie blokować kursora
            if result is None:
                self.label_2.setText("Nie znaleziono pojazdu w bazie danych")
                return

            slot_no = int(result[0])
            slots[slot_no - 1] = False  # Oznaczenie slotu jako wolny
            car_numbers[slot_no - 1] = None

            # Usunięcie pojazdu z bazy danych
            mycursor.execute("DELETE FROM slot WHERE carNumber = %s", (rejestracja,))
            mycursor.fetchall()  # Odczytaj pozostałe wyniki, aby nie blokować kursora
            mycursor.execute("DELETE FROM entry WHERE carNumber = %s", (rejestracja,))
            mycursor.fetchall()  # Odczytaj pozostałe wyniki, aby nie blokować kursora

            self.label_2.setText(f"Zarejestrowano wyjazd dla: {rejestracja} (Miejsce: {slot_no})")

            # Aktualizacja przycisku miejsca parkingowego
            self.update_slot_buttons()

            # Usunięcie numeru rejestracyjnego z listy wyboru
            index = self.comboBoxRejestracja.findText(rejestracja)
            if index >= 0:
                self.comboBoxRejestracja.removeItem(index)

    def update_slot_buttons(self):
        # Aktualizacja stanu przycisków miejsc parkingowych
        for i in range(5):
            button_name = f"s{i + 1}"
            button = self.findChild(QtWidgets.QPushButton, button_name)
            if button:
                if slots[i]:
                    button.setStyleSheet("background-color: #FF0B00")  # czerwony - zajęty
                    button.setText(car_numbers[i])  # Ustawienie numeru rejestracyjnego
                else:
                    button.setStyleSheet("background-color: #40FF50")  # zielony - wolny
                    button.setText(f"S{i + 1}")


def main():
    app = QtWidgets.QApplication(sys.argv)
    window = Ui()
    window.show()
    app.exec_()


if __name__ == "__main__":
    main()