import mysql.connector
import datetime
import sys
import re
import time

from PyQt5 import QtCore, QtWidgets, uic

# Połączenie z bazą danych
mydb = mysql.connector.connect(host="localhost", user="root", passwd="root", database="car", autocommit=True)
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
slots = [False for _ in range(16)]


class Ui(QtWidgets.QMainWindow):
    def __init__(self):
        super(Ui, self).__init__()
        uic.loadUi("C:/Users/vene/Desktop/praca_parking/automatic_parking_system/front.ui", self)

        # Połączenie przycisków z funkcjami
        self.ENTRYBUTTON.released.connect(self.handle_entry)
        self.EXITBUTTON.released.connect(self.handle_exit)

    def handle_entry(self):
        car_number = self.lineEdit.text()
        mycursor.execute("SELECT carNumber FROM slot")
        existing_numbers = list(mycursor.fetchall())

        # Sprawdzenie, czy numer pojazdu już istnieje
        if any(car_number in s for s in existing_numbers):
            self.label_2.setText("Duplicate")
        else:
            self.process_entry(car_number)

    def process_entry(self, car_number):
        if len(car_number) == 0:
            self.label_2.setText("Empty")
        else:
            self.register_entry(car_number)

    def register_entry(self, car_number):
        try:
            # Znalezienie pierwszego dostępnego miejsca
            slot_no = int(slots.index(False))
            slots[slot_no] = True
            slot_no += 1

            # Zarejestrowanie czasu wjazdu
            entry_time = datetime.datetime.now()

            # Dodanie wpisów do bazy danych
            mycursor.execute("INSERT INTO slot (carNumber, slot) VALUES (%s, %s)", (car_number, slot_no))
            mycursor.execute("INSERT INTO entry (carNumber, entry) VALUES (%s, %s)", (car_number, entry_time))
            mycursor.execute("INSERT INTO exits (carNumber) VALUES (%s)", (car_number,))
            mycursor.execute("INSERT INTO duration (carNumber) VALUES (%s)", (car_number,))
            mycursor.execute("INSERT INTO cost (carNumber) VALUES (%s)", (car_number,))

            self.label_2.setText(f"Slot: {slot_no}")

            # Aktualizacja wyglądu przycisków
            self.update_slot_buttons()
        except Exception as e:
            print(e)
            self.label_2.setText("Invalid")

    def handle_exit(self):
        try:
            car_number = self.lineEdit.text()
            self.lineEdit.clear()

            # Zarejestrowanie czasu wyjazdu
            exit_time = datetime.datetime.now()
            mycursor.execute("UPDATE exits SET exit1 = %s WHERE carNumber = %s", (exit_time, car_number))

            # Znalezienie numeru miejsca parkingowego
            mycursor.execute("SELECT slot FROM slot WHERE carNumber = %s", (car_number,))
            slot_no = int(re.sub("[^0-9]", "", str(mycursor.fetchone())))
            slots[slot_no - 1] = False

            # Obliczenie czasu parkowania
            mycursor.execute("SELECT entry FROM entry WHERE carNumber = %s", (car_number,))
            entry_time = re.sub("[,)(']", "", str(mycursor.fetchone()))
            entry_time = datetime.datetime.fromisoformat(entry_time)

            duration = int((exit_time - entry_time).total_seconds())
            cost = min(150, 10 * duration)
            self.label_2.setText(f"Cost: Rs.{cost}")

            # Aktualizacja wpisów w bazie danych
            mycursor.execute("UPDATE duration SET durationInSec = %s WHERE carNumber = %s", (duration, car_number))
            mycursor.execute("UPDATE cost SET cost = %s WHERE carNumber = %s", (cost, car_number))

            # Aktualizacja wyglądu przycisków
            self.update_slot_buttons()
        except Exception as e:
            print(e)
            self.label_2.setText("Invalid Entry")

    def update_slot_buttons(self):
        # Aktualizacja stanu przycisków miejsc parkingowych
        for i in range(16):
            button_name = f"s{i + 1}"
            button = self.findChild(QtWidgets.QPushButton, button_name)
            if button:
                if slots[i]:
                    button.setStyleSheet("background-color: #FF0B00")  # czerwony - zajęty
                else:
                    button.setStyleSheet("background-color: #40FF50")  # zielony - wolny


def main():
    app = QtWidgets.QApplication(sys.argv)
    window = Ui()
    window.show()
    app.exec_()


if __name__ == "__main__":
    main()
