import requests
from bs4 import BeautifulSoup
import re
import os
from dotenv import load_dotenv
import json
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

load_dotenv()


class SwadharmaLogin:
    BASE_URL = "https://spada.swadharma.ac.id"
    LOGIN_URL = f"{BASE_URL}/login/index.php"
    SERVICE_URL = f"{BASE_URL}/lib/ajax/service.php"

    def __init__(self, username, password, userid):
        self.username = username
        self.password = password
        self.userid = userid
        self.session = requests.Session()
        self.logintoken = None
        self.sesskey = None

    def fetch_login_page_details(self):
        """
        Mengambil halaman login untuk mendapatkan logintoken dan MoodleSession cookie.
        """
        logging.info("Mencoba mengambil halaman login...")
        try:
            response = self.session.get(self.LOGIN_URL)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            logintoken_input = soup.find(
                "input", {"name": "logintoken", "type": "hidden"}
            )
            if logintoken_input:
                self.logintoken = logintoken_input["value"]
                logging.info(f"logintoken berhasil diambil: {self.logintoken}")
            else:
                raise ValueError("logintoken tidak ditemukan di halaman login.")

            logging.info(f"MoodleSession cookie secara otomatis disimpan oleh session.")
            if "MoodleSession" in self.session.cookies:
                logging.info(
                    f"Current MoodleSession: {self.session.cookies['MoodleSession']}"
                )

            return True
        except requests.exceptions.RequestException as e:
            logging.error(f"Gagal mengambil halaman login: {e}")
            return False
        except ValueError as e:
            logging.error(f"Error: {e}")
            return False

    def perform_login(self):
        """
        Mengirimkan permintaan POST untuk melakukan proses login.
        Mengembalikan URL pengalihan jika berhasil, atau None jika gagal.
        """
        if not self.logintoken:
            logging.error(
                "Error: logintoken belum diambil. Harap panggil fetch_login_page_details() terlebih dahulu."
            )
            return None

        logging.info("Mencoba melakukan login...")
        login_data = {
            "logintoken": self.logintoken,
            "username": self.username,
            "password": self.password,
        }

        headers = {
            "Host": "spada.swadharma.ac.id",
            "Cache-Control": "max-age=0",
            "Sec-Ch-Ua": '"Not.A/Brand";v="99", "Chromium";v="136"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": "macOS",
            "Accept-Language": "en-US,en;q=0.9",
            "Origin": "https://spada.swadharma.ac.id",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        try:
            response = self.session.post(
                self.LOGIN_URL, data=login_data, headers=headers, allow_redirects=False
            )
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            redirect_link_tag = soup.find("a", href=re.compile(r"testsession="))

            if redirect_link_tag:
                full_redirect_url = redirect_link_tag["href"]
                logging.info(
                    f"Login berhasil, mendeteksi pengalihan ke: {full_redirect_url}"
                )
                return full_redirect_url
            else:
                logging.error(
                    "Login gagal atau pengalihan tidak ditemukan. Respon HTML:"
                )
                logging.error(response.text[:500])
                return None

        except requests.exceptions.RequestException as e:
            logging.error(f"Gagal melakukan permintaan login POST: {e}")
            return None

    def follow_redirect_and_get_sesskey(self, redirect_url):
        """
        Mengakses URL pengalihan (testsession) untuk mendapatkan sesskey.
        """
        logging.info(
            f"Mengikuti pengalihan dan mencoba mendapatkan sesskey dari: {redirect_url}"
        )
        try:
            response = self.session.get(redirect_url)
            response.raise_for_status()
            sesskey_match = re.search(r'"sesskey":"([a-zA-Z0-9]+)"', response.text)

            if sesskey_match:
                self.sesskey = sesskey_match.group(1)
                logging.info(f"sesskey berhasil diambil: {self.sesskey}")
                return True
            else:
                logging.error("sesskey tidak ditemukan di halaman pengalihan.")
                return False

        except requests.exceptions.RequestException as e:
            logging.error(f"Gagal mengikuti pengalihan atau mendapatkan sesskey: {e}")
            return False

    def test_login_status(self):
        """
        Menguji status login dengan memanggil API core_course_get_recent_courses.
        """
        if not self.sesskey:
            logging.error(
                "Error: sesskey belum diambil. Harap selesaikan proses login terlebih dahulu."
            )
            return False

        logging.info(
            "Mencoba menguji status login dengan memanggil API kursus terbaru..."
        )
        api_url = f"{self.SERVICE_URL}?sesskey={self.sesskey}&info=core_course_get_recent_courses"

        api_body = [
            {
                "index": 0,
                "methodname": "core_course_get_recent_courses",
                "args": {"userid": self.userid, "limit": 10},
            }
        ]

        headers = {
            "Content-Type": "application/json",
            "Host": "spada.swadharma.ac.id",
            "Cache-Control": "max-age=0",
            "Sec-Ch-Ua": '"Not.A/Brand";v="99", "Chromium";v="136"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": "macOS",
            "Accept-Language": "en-US,en;q=0.9",
            "Origin": "https://spada.swadharma.ac.id",
        }

        try:
            response = self.session.post(api_url, json=api_body, headers=headers)
            response.raise_for_status()

            response_json = response.json()
            logging.info("Respons API (Kursus Terbaru)")

            if (
                response_json
                and isinstance(response_json, list)
                and len(response_json) > 0
            ):
                if "error" in response_json[0] and response_json[0]["error"] is True:
                    logging.error(
                        f"API mengembalikan error: {response_json[0]['error']}"
                    )
                    return False
                # Periksa apakah ada 'data' dan 'data' itu sendiri adalah list (daftar kursus)
                elif (
                    "data" in response_json[0]
                    and isinstance(response_json[0]["data"], list)
                    and len(response_json[0]["data"]) > 0
                ):
                    logging.info("Berhasil mengambil daftar kursus terbaru!")
                    return True
                else:
                    logging.error(
                        "Respons API tidak sesuai format yang diharapkan atau tidak ada data kursus yang valid."
                    )
                    return False
            else:
                logging.error("Respons API kosong atau tidak valid.")
                return False

        except requests.exceptions.RequestException as e:
            logging.error(f"Gagal menguji status login dengan API: {e}")
            return False
        except json.JSONDecodeError:
            logging.error("Gagal mengurai respons JSON dari API.")
            logging.error(f"Respon mentah: {response.text[:500]}")
            return False


# Contoh penggunaan
if __name__ == "__main__":
    USERNAME = os.getenv("SPADA_USERNAME")
    PASSWORD = os.getenv("SPADA_PASSWORD")
    USERID = os.getenv("SPADA_USERID")

    if not all([USERNAME, PASSWORD, USERID]):
        logging.error(
            "Error: Kredensial (USERNAME, PASSWORD, USERID) tidak ditemukan di variabel lingkungan."
        )
        logging.error(
            "Pastikan Anda memiliki file .env di direktori yang sama dengan isian yang benar."
        )
        exit(1)

    login_manager = SwadharmaLogin(USERNAME, PASSWORD, USERID)

    if login_manager.fetch_login_page_details():
        redirect_url = login_manager.perform_login()
        if redirect_url:
            logging.info(f"Login awal berhasil. URL pengalihan: {redirect_url}")
            if login_manager.follow_redirect_and_get_sesskey(redirect_url):
                logging.info("Berhasil mendapatkan sesskey. Login selesai!")
                if login_manager.test_login_status():
                    logging.info("Verifikasi login berhasil dengan API kursus terbaru!")
                else:
                    logging.error("Verifikasi login dengan API kursus terbaru gagal.")
            else:
                logging.error("Gagal mendapatkan sesskey.")
        else:
            logging.error("Login awal gagal.")
    else:
        logging.error("\\nProses pengambilan detail halaman login gagal.")
