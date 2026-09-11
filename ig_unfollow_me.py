import os
import sys
import time
import traceback

import pandas as pd
import uiautomator2 as u2

from numpy.random import uniform
from loguru import logger
from tqdm import tqdm

# ============================================================
# CONFIGURACIÓN
# ============================================================

# Archivo con las cuentas que queremos eliminar
CSV_FILE = "cuentas.csv"

# ------------------------------------------------------------
# PRUEBA
#
# 1 = solamente la primera cuenta
# 0 = TODAS las cuentas
#
# IMPORTANTE:
# Primero probar con 1.
# ------------------------------------------------------------

TEST_LIMIT = 0

# Tiempo aleatorio entre acciones
DELAY_LOWER = 2.0
DELAY_UPPER = 5.0

# Paquete de Instagram
INSTAGRAM_PACKAGE = "com.instagram.android"

# ============================================================
# CARPETA DE LOGS
# ============================================================

os.makedirs("log", exist_ok=True)

# ============================================================
# LOG
# ============================================================

logger.remove()

logger.add(
   sys.stdout,
   format=(
       "<level>[{time:HH:mm:ss.SSS}]</level> "
       "<cyan>{function}</cyan> "
       "<yellow>L{line}</yellow> "
       "{message}"
   ),
   colorize=True,
   backtrace=True,
   diagnose=True,
)

logger.add(
   "log/Instagram_RemoveFollowers_{time:YYYYMMDD-HHmmss}.log",
   format=(
       "[{time:YYYY/MM/DD HH:mm:ss.SSS}] "
       "{function} L{line} "
       "{message}"
   ),
   colorize=False,
   backtrace=True,
   diagnose=True,
)

# ============================================================
# CLASE
# ============================================================

class InstagramFollowerRemover:

   def __init__(self):

       self.device = None
       self.users = []
       self.results = []

   # ========================================================
   # DELAY ALEATORIO
   # ========================================================

   def random_delay(self):

       return uniform(
           DELAY_LOWER,
           DELAY_UPPER
       )

   # ========================================================
   # LEER CUENTAS.CSV
   # ========================================================

   def load_accounts(self):

       logger.info(
           f'Leyendo "{CSV_FILE}"...'
       )

       if not os.path.exists(CSV_FILE):

           logger.error(
               f'No encuentro "{CSV_FILE}".'
           )

           logger.error(
               "El archivo debe estar en la misma carpeta "
               "que este programa."
           )

           return False

       # ----------------------------------------------------
       # Intentar UTF-8
       # ----------------------------------------------------

       try:

           df = pd.read_csv(
               CSV_FILE,
               encoding="utf-8-sig"
           )

       except Exception:

           try:

               df = pd.read_csv(
                   CSV_FILE,
                   encoding="latin-1"
               )

           except Exception as exc:

               logger.error(
                   f"No pude leer {CSV_FILE}: {exc}"
               )

               return False

       logger.info(
           f"Columnas encontradas: {list(df.columns)}"
       )

       # ----------------------------------------------------
       # Buscar automáticamente la columna de usuario
       # ----------------------------------------------------

       possible_names = [
           "user",
           "username",
           "usuario",
           "cuenta",
           "account",
           "nombre",
           "name"
       ]

       selected_column = None

       for column in df.columns:

           column_normalized = (
               str(column)
               .strip()
               .lower()
           )

           if column_normalized in possible_names:

               selected_column = column
               break

       # ----------------------------------------------------
       # Si no encontramos nombre conocido,
       # usamos la primera columna.
       # ----------------------------------------------------

       if selected_column is None:

           selected_column = df.columns[0]

           logger.warning(
               "No encontré una columna llamada "
               "'user', 'username', etc."
           )

           logger.warning(
               f'Usaré la primera columna: "{selected_column}"'
           )

       else:

           logger.info(
               f'Usando columna "{selected_column}"'
           )

       # ----------------------------------------------------
       # Extraer usuarios
       # ----------------------------------------------------

       users = (
           df[selected_column]
           .dropna()
           .astype(str)
           .str.strip()
       )

       # Eliminar vacíos
       users = users[
           (users != "") &
           (users.str.lower() != "nan") &
           (users.str.lower() != "none")
       ]

       # Eliminar duplicados
       users = list(
           dict.fromkeys(
               users.tolist()
           )
       )

       # ----------------------------------------------------
       # Límite de prueba
       # ----------------------------------------------------

       if TEST_LIMIT > 0:

           logger.warning(
               f"TEST_LIMIT = {TEST_LIMIT}"
           )

           logger.warning(
               "SOLO SE PROCESARÁ LA PRIMERA CUENTA."
           )

           users = users[:TEST_LIMIT]

       self.users = users

       logger.success(
           f"Se cargaron {len(self.users)} cuentas."
       )

       logger.info(
           "Cuentas a procesar:"
       )

       for user in self.users[:20]:

           logger.info(
               f"    {user}"
           )

       if len(self.users) > 20:

           logger.info(
               f"... y {len(self.users) - 20} más."
           )

       return len(self.users) > 0

   # ========================================================
   # CONECTAR POR USB
   # ========================================================

   def connect_usb(self):

       logger.info(
           "Conectando con el teléfono mediante USB..."
       )

       try:

           # ------------------------------------------------
           # SIN IP.
           #
           # uiautomator2 buscará el dispositivo conectado
           # por ADB/USB.
           # ------------------------------------------------

           self.device = u2.connect()

           logger.success(
               "Teléfono conectado correctamente."
           )

           try:

               logger.info(
                   f"Modelo: {self.device.info.get('productName')}"
               )

               logger.info(
                   f"Android: {self.device.info.get('version')}"
               )

           except Exception:

               logger.info(
                   f"Device info: {self.device.info}"
               )

           return True

       except Exception as exc:

           logger.error(
               "No pude conectar con el teléfono."
           )

           logger.error(
               str(exc)
           )

           logger.error(
               ""
           )

           logger.error(
               "Verificá:"
           )

           logger.error(
               "1. Que el teléfono esté conectado por USB."
           )

           logger.error(
               "2. Que la Depuración USB esté activada."
           )

           logger.error(
               "3. Que hayas aceptado 'Permitir depuración USB' "
               "en el teléfono."
           )

           logger.error(
               "4. Que ADB detecte el teléfono."
           )

           return False

   # ========================================================
   # BUSCAR PRIMER ELEMENTO
   # ========================================================

   def find_first(
       self,
       selectors,
       timeout=2
   ):

       for selector in selectors:

           try:

               element = self.device(
                   **selector
               )

               if element.exists(
                   timeout=timeout
               ):

                   return element

           except Exception:

               continue

       return None

   # ========================================================
   # ESPERAR ELEMENTO
   # ========================================================

   def wait_for_element(
       self,
       selectors,
       timeout=10
   ):

       deadline = (
           time.time() + timeout
       )

       while time.time() < deadline:

           element = self.find_first(
               selectors,
               timeout=0.5
           )

           if element is not None:

               return element

           time.sleep(0.3)

       return None

   # ========================================================
   # ABRIR INSTAGRAM
   # ========================================================

   def open_instagram(self):

       logger.info(
           "Abriendo Instagram..."
       )

       try:

           self.device.app_start(
               INSTAGRAM_PACKAGE
           )

           time.sleep(5)

           logger.success(
               "Instagram abierto."
           )

           return True

       except Exception as exc:

           logger.error(
               f"No pude abrir Instagram: {exc}"
           )

           return False

   # ========================================================
   # ABRIR PERFIL
   # ========================================================

   def open_profile(self):

       logger.info(
           "Buscando Perfil..."
       )

       selectors = [

           {
               "description": "Profile"
           },

           {
               "description": "Perfil"
           },

           {
               "descriptionContains": "Profile"
           },

           {
               "descriptionContains": "Perfil"
           },

           {
               "text": "Profile"
           },

           {
               "text": "Perfil"
           }

       ]

       profile = self.wait_for_element(
           selectors,
           timeout=8
       )

       if profile is not None:

           try:

               profile.click()

               time.sleep(2)

               logger.success(
                   "Perfil abierto."
               )

               return True

           except Exception as exc:

               logger.warning(
                   f"No pude hacer click en Perfil: {exc}"
               )

       # ----------------------------------------------------
       # FALLBACK
       # ----------------------------------------------------

       logger.warning(
           "No encontré Perfil mediante UI."
       )

       logger.warning(
           "Intentando botón inferior derecho..."
       )

       try:

           width, height = (
               self.device.window_size()
           )

           self.device.click(
               int(width * 0.90),
               int(height * 0.94)
           )

           time.sleep(2)

           logger.success(
               "Intenté abrir Perfil mediante posición."
           )

           return True

       except Exception as exc:

           logger.error(
               f"No pude abrir Perfil: {exc}"
           )

           return False

   # ========================================================
   # ABRIR SEGUIDORES
   # ========================================================

   def open_followers(self):

       logger.info(
           "Buscando 'Seguidores'..."
       )

       selectors = [

           {
               "text": "Seguidores"
           },

           {
               "text": "Followers"
           },

           {
               "textContains": "seguidores"
           },

           {
               "textContains": "Followers"
           },

           {
               "description": "Seguidores"
           },

           {
               "description": "Followers"
           },

           {
               "descriptionContains": "Seguidores"
           },

           {
               "descriptionContains": "Followers"
           }

       ]

       followers = self.wait_for_element(
           selectors,
           timeout=10
       )

       if followers is None:

           logger.error(
               "No encontré el botón Seguidores."
           )

           return False

       try:

           followers.click()

           time.sleep(2)

           logger.success(
               "Lista de Seguidores abierta."
           )

           return True

       except Exception as exc:

           logger.error(
               f"No pude abrir Seguidores: {exc}"
           )

           return False

   # ========================================================
   # BUSCADOR
   # ========================================================

   def get_search_box(self):

       selectors = [

           {
               "resourceId":
               "com.instagram.android:id/"
               "action_bar_search_edit_text"
           },

           {
               "className":
               "android.widget.EditText"
           },

           {
               "text": "Buscar"
           },

           {
               "text": "Search"
           },

           {
               "description": "Buscar"
           },

           {
               "description": "Search"
           }

       ]

       return self.find_first(
           selectors,
           timeout=2
       )

   # ========================================================
   # PREPARAR PANTALLA
   # ========================================================

   def setup_followers(self):

       if not self.open_instagram():

           return False

       # ----------------------------------------------------
       # Perfil
       # ----------------------------------------------------

       if not self.open_profile():

           return False

       time.sleep(1)

       # ----------------------------------------------------
       # Seguidores
       # ----------------------------------------------------

       if not self.open_followers():

           return False

       time.sleep(1)

       # ----------------------------------------------------
       # Comprobar buscador
       # ----------------------------------------------------

       search = self.wait_for_element(
           [
               {
                   "className":
                   "android.widget.EditText"
               },

               {
                   "text": "Buscar"
               },

               {
                   "text": "Search"
               }

           ],
           timeout=5
       )

       if search is None:

           logger.error(
               "No encontré la barra de búsqueda."
           )

           return False

       logger.success(
           "Pantalla de Seguidores lista."
       )

       return True

   # ========================================================
   # LIMPIAR BUSCADOR
   # ========================================================

   def clear_search(self):

       search = self.get_search_box()

       if search is None:

           logger.warning(
               "No encontré el buscador para limpiar."
           )

           return False

       try:

           search.click()

           time.sleep(0.2)

           search.clear_text()

           time.sleep(0.3)

           return True

       except Exception as exc:

           logger.warning(
               f"No pude limpiar el buscador: {exc}"
           )

           return False

   # ========================================================
   # BUSCAR USUARIO
   # ========================================================

   def search_user(
       self,
       username
   ):

       logger.info(
           f'Buscando "{username}"...'
       )

       search = self.get_search_box()

       if search is None:

           logger.error(
               "No encontré la barra de búsqueda."
           )

           return None

       try:

           search.click()

           time.sleep(0.3)

           search.clear_text()

           time.sleep(0.3)

           search.set_text(
               username
           )

       except Exception as exc:

           logger.error(
               f'No pude escribir "{username}": {exc}'
           )

           return None

       # ----------------------------------------------------
       # Esperar resultados
       # ----------------------------------------------------

       time.sleep(1.5)

       # ----------------------------------------------------
       # Username exacto
       # ----------------------------------------------------

       user = self.device(
           text=username
       )

       if user.exists(
           timeout=4
       ):

           logger.success(
               f'Encontré "{username}".'
           )

           return user

       # ----------------------------------------------------
       # Alternativa
       # ----------------------------------------------------

       user = self.device(
           description=username
       )

       if user.exists(
           timeout=2
       ):

           logger.success(
               f'Encontré "{username}".'
           )

           return user

       logger.warning(
           f'No encontré "{username}" entre los seguidores.'
       )

       return None

   # ========================================================
   # OBTENER COORDENADAS
   # ========================================================

   def get_bounds(
       self,
       element
   ):

       try:

           bounds = (
               element.info
               .get("bounds")
           )

           if bounds:

               return bounds

       except Exception:

           pass

       return None

   # ========================================================
   # ¿ESTÁ ABIERTO EL DIÁLOGO?
   # ========================================================

   def remove_dialog_visible(self):

       selectors = [

           {
               "text": "¿Eliminar seguidor?"
           },

           {
               "textContains":
               "Eliminar seguidor"
           },

           {
               "textContains":
               "eliminar seguidor"
           },

           {
               "textContains":
               "Remove follower"
           },

           {
               "textContains":
               "Remove follower?"
           }

       ]

       element = self.find_first(
           selectors,
           timeout=0.5
       )

       return element is not None

   # ========================================================
   # TOCAR LA X
   # ========================================================

   def click_remove_x(
       self,
       username,
       user_element
   ):

       # --------------------------------------------------------
       # Instagram puede devolver para el username un bounds cuyo
       # Y no coincide exactamente con la posición visual de la
       # fila. En la versión que estás usando, el botón X aparece
       # aproximadamente 100 px por debajo del centro devuelto.
       #
       # En vez de usar únicamente center_y, probamos varios Y
       # relativos y verificamos SIEMPRE el diálogo antes de seguir.
       # --------------------------------------------------------

       bounds = self.get_bounds(
           user_element
       )

       if bounds is None:
           logger.error(
               f"No pude obtener posición de {username}."
           )
           return False

       try:
           top = int(bounds["top"])
           bottom = int(bounds["bottom"])
           center_y = int((top + bottom) / 2)

           width, height = self.device.window_size()

           logger.info(
               f'Fila de "{username}" encontrada.'
           )
           logger.info(
               f"Bounds username: {bounds}"
           )
           logger.info(
               f"Centro original: X=?, Y={center_y}"
           )
           logger.info(
               f"Pantalla: {width}x{height}"
           )

       except Exception as exc:
           logger.error(
               f"No pude calcular la posición de {username}: {exc}"
           )
           return False

       # --------------------------------------------------------
       # POSICIONES X
       #
       # En la captura la X está prácticamente pegada al borde
       # derecho de la pantalla.
       # --------------------------------------------------------

       x_positions = [
           int(width - 25),
           int(width - 30),
           int(width - 35),
           int(width - 40),
           int(width - 45),
       ]

       # --------------------------------------------------------
       # POSICIONES Y
       #
       # Primero probamos el centro original.
       # Luego el desplazamiento proporcional que corresponde a
       # la diferencia observada en tu teléfono (~98 px en una
       # pantalla de 1600 px de alto).
       #
       # También dejamos algunos valores vecinos para tolerar
       # pequeñas diferencias de versión/escala de Instagram.
       # --------------------------------------------------------

       y_offset = int(height * 0.06125)

       y_positions = [
           center_y + y_offset,
           center_y + int(height * 0.055),
           center_y + int(height * 0.067),
           center_y + int(height * 0.050),
           center_y + int(height * 0.073),
           center_y,
       ]

       # Eliminar duplicados conservando el orden
       y_positions = list(dict.fromkeys(y_positions))

       logger.info(
           f"Y original: {center_y}"
       )
       logger.info(
           f"Offset Y: +{y_offset}"
       )
       logger.info(
           f"Y a probar: {y_positions}"
       )

       # --------------------------------------------------------
       # PROBAR X/Y
       # --------------------------------------------------------

       for y in y_positions:

           for x in x_positions:

               logger.info(
                   f"Probando botón X en ({x}, {y})"
               )

               try:
                   self.device.click(
                       x,
                       y
                   )

               except Exception as exc:
                   logger.warning(
                       f"Click falló en ({x}, {y}): {exc}"
                   )
                   continue

               # Dar tiempo a Instagram para abrir el diálogo
               time.sleep(0.8)

               # ------------------------------------------------
               # VERIFICACIÓN CRÍTICA
               #
               # No consideramos que el botón fue pulsado hasta
               # que aparezca el diálogo "Eliminar seguidor".
               # ------------------------------------------------

               if self.remove_dialog_visible():

                   logger.success(
                       f"Diálogo de eliminación abierto para "
                       f'"{username}" en ({x}, {y}).'
                   )

                   return True

       logger.error(
           f"No pude abrir el diálogo para {username}."
       )

       logger.error(
           "Se agotaron todas las posiciones X/Y de prueba."
       )

       return False

   # ========================================================
   # CONFIRMAR ELIMINACIÓN
   # ========================================================

   def confirm_remove(
       self,
       username
   ):

       # ----------------------------------------------------
       # Verificar diálogo
       # ----------------------------------------------------

       if not self.remove_dialog_visible():

           logger.error(
               "No detecté el diálogo de confirmación."
           )

           return False

       logger.info(
           "Buscando botón 'Eliminar'..."
       )

       selectors = [

           {
               "text": "Eliminar"
           },

           {
               "description": "Eliminar"
           },

           {
               "text": "Remove"
           },

           {
               "description": "Remove"
           }

       ]

       button = self.wait_for_element(
           selectors,
           timeout=3
       )

       if button is None:

           logger.error(
               "No encontré el botón 'Eliminar'."
           )

           return False

       try:

           button.click()

       except Exception as exc:

           logger.error(
               f"No pude pulsar 'Eliminar': {exc}"
           )

           return False

       time.sleep(1.5)

       # ----------------------------------------------------
       # Verificar que desapareció.
       # ----------------------------------------------------

       if self.remove_dialog_visible():

           logger.error(
               f'El diálogo continúa abierto para "{username}".'
           )

           return False

       logger.success(
           f'"{username}" eliminado correctamente.'
       )

       return True

   # ========================================================
   # ELIMINAR UN SEGUIDOR
   # ========================================================

   def remove_follower(
       self,
       username
   ):

       # ----------------------------------------------------
       # Buscar
       # ----------------------------------------------------

       user_element = self.search_user(
           username
       )

       if user_element is None:

           return False, "not_found"

       # ----------------------------------------------------
       # Espera
       # ----------------------------------------------------

       time.sleep(
           self.random_delay()
       )

       # ----------------------------------------------------
       # X
       # ----------------------------------------------------

       if not self.click_remove_x(
           username,
           user_element
       ):

           return False, "remove_button_failed"

       # ----------------------------------------------------
       # Confirmación
       # ----------------------------------------------------

       time.sleep(0.5)

       if not self.confirm_remove(
           username
       ):

           return False, "confirmation_failed"

       return True, "removed"

   # ========================================================
   # GUARDAR RESULTADOS
   # ========================================================

   def save_results(self):

       if not self.results:

           return

       filename = pd.Timestamp.now().strftime(
           "log/resultado_%Y%m%d-%H%M%S.csv"
       )

       try:

           df = pd.DataFrame(
               self.results
           )

           df.to_csv(
               filename,
               index=False,
               encoding="utf-8-sig"
           )

           logger.success(
               f'Resultados guardados en "{filename}"'
           )

       except Exception as exc:

           logger.error(
               f"No pude guardar resultados: {exc}"
           )

   # ========================================================
   # RUN
   # ========================================================

   def run(self):

       logger.info(
           ""
       )

       logger.info(
           "=" * 70
       )

       logger.info(
           "INSTAGRAM - ELIMINAR SEGUIDORES"
       )

       logger.info(
           "=" * 70
       )

       # ----------------------------------------------------
       # Cargar CSV
       # ----------------------------------------------------

       if not self.load_accounts():

           return

       # ----------------------------------------------------
       # Conectar por USB
       # ----------------------------------------------------

       if not self.connect_usb():

           return

       # ----------------------------------------------------
       # Preparar Instagram
       # ----------------------------------------------------

       if not self.setup_followers():

           logger.error(
               "No pude llegar a la pantalla de Seguidores."
           )

           return

       # ----------------------------------------------------
       # Espera inicial
       # ----------------------------------------------------

       logger.warning(
           "Todo está listo."
       )

       logger.warning(
           f"Comenzando en {DELAY_UPPER:.1f} segundos..."
       )

       time.sleep(
           DELAY_UPPER
       )

       # ----------------------------------------------------
       # Procesar
       # ----------------------------------------------------

       progress = tqdm(
           self.users,
           total=len(self.users),
           desc="Seguidores"
       )

       for username in progress:

           username = str(
               username
           ).strip()

           if not username:

               continue

           start_time = time.time()

           progress.set_description(
               f"Procesando {username}"
           )

           result = {
               "username": username,
               "status": "",
               "message": "",
               "timestamp": pd.Timestamp.now()
           }

           try:

               logger.info(
                   ""
               )

               logger.info(
                   "#" * 70
               )

               logger.info(
                   f'PROCESANDO: "{username}"'
               )

               logger.info(
                   "#" * 70
               )

               success, status = (
                   self.remove_follower(
                       username
                   )
               )

               result["status"] = status

               result["seconds"] = round(
                   time.time() - start_time,
                   2
               )

               if success:

                   result["message"] = (
                       "Follower removed successfully"
                   )

                   progress.set_description(
                       f"OK {username}"
                   )

                   logger.success(
                       f'FINALIZADO: "{username}"'
                   )

               else:

                   result["message"] = (
                       "Could not remove follower"
                   )

                   progress.set_description(
                       f"FALLO {username}"
                   )

                   logger.warning(
                       f'NO ELIMINADO: "{username}" '
                       f"({status})"
                   )

               self.results.append(
                   result
               )

           except KeyboardInterrupt:

               logger.warning(
                   "Proceso detenido manualmente."
               )

               result["status"] = (
                   "interrupted"
               )

               result["message"] = (
                   "Stopped manually"
               )

               self.results.append(
                   result
               )

               break

           except Exception as exc:

               logger.exception(
                   f'Error procesando "{username}": {exc}'
               )

               result["status"] = (
                   "error"
               )

               result["message"] = str(
                   exc
               )

               result["seconds"] = round(
                   time.time() - start_time,
                   2
               )

               self.results.append(
                   result
               )

           # ------------------------------------------------
           # Limpiar buscador
           # ------------------------------------------------

           time.sleep(
               self.random_delay()
           )

           self.clear_search()

           time.sleep(
               0.5
           )

       # ----------------------------------------------------
       # Guardar
       # ----------------------------------------------------

       self.save_results()

       # ----------------------------------------------------
       # Resumen
       # ----------------------------------------------------

       total = len(
           self.results
       )

       removed = sum(
           1
           for r in self.results
           if r["status"] == "removed"
       )

       not_found = sum(
           1
           for r in self.results
           if r["status"] == "not_found"
       )

       errors = (
           total
           - removed
           - not_found
       )

       logger.info(
           ""
       )

       logger.info(
           "=" * 70
       )

       logger.success(
           "PROCESO TERMINADO"
       )

       logger.info(
           f"Procesadas:    {total}"
       )

       logger.info(
           f"Eliminadas:    {removed}"
       )

       logger.info(
           f"No encontradas: {not_found}"
       )

       logger.info(
           f"Errores:       {errors}"
       )

       logger.info(
           "=" * 70
       )

# ============================================================
# EJECUTAR
# ============================================================

if __name__ == "__main__":

   try:

       app = InstagramFollowerRemover()

       app.run()

   except KeyboardInterrupt:

       logger.warning(
           "Programa detenido."
       )

   except Exception as exc:

       logger.exception(
           f"Error inesperado: {exc}"
       )

       traceback.print_exc()

       input(
           "\nPresioná ENTER para cerrar..."
       )