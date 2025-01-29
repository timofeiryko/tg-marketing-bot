import gspread
from oauth2client.service_account import ServiceAccountCredentials
import sys
from pathlib import Path
from backend import TelegramUser, init, shutdown
import asyncio

def init_sheet():

    # Define the scope and authenticate using the `credentials.json`.
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credentials = ServiceAccountCredentials.from_json_keyfile_name('home-health-428712-f1cc4fa665d3.json', scope)
    client = gspread.authorize(credentials)

    print("Authenticated successfully.")

    # Open the Google Sheet by URL or key.
    spreadsheet = client.open_by_url('https://docs.google.com/spreadsheets/d/1Fsa8bXo7Vp9nDzaBpuOTDsSPb_jndFCYnGXxAgKP7HI/edit?usp=sharing')

    # Specify the worksheet to update data.
    worksheet = spreadsheet.worksheet('БИОЛОГИЯ')

    return worksheet

def append_user(user: TelegramUser):

    # Initialize the worksheet.
    worksheet = init_sheet()

    # Append the user to the worksheet.
    has_payed = 'Да' if user.has_payed_for_intensive else 'Нет'
    row = [user.id, user.first_name, user.last_name, user.username, user.telegram_id, user.email, has_payed]

    worksheet.append_row(row)

async def populate_sheet():

    # Initialize the worksheet.
    worksheet = init_sheet()

    # Clear the worksheet (except the header).
    header = worksheet.row_values(1)
    worksheet.clear()
    worksheet.append_row(header)

    # Get all users from the database.
    users = await TelegramUser.all()

    # Append all users to the worksheet.
    for user in users:
        has_payed = 'Да' if user.has_payed_for_intensive else 'Нет'
        worksheet.append_row([user.id, user.first_name, user.last_name, user.username, user.telegram_id, user.email, has_payed])

    return

async def main():

    await init()

    await populate_sheet()
    print("Sheet updated successfully.")

    # Close the connection.
    await shutdown()

    # Exit the script.
    asyncio.get_event_loop().stop()


if __name__ == '__main__':
    asyncio.run(main())