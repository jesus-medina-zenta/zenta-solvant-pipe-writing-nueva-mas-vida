from src.services.sftp_service import SFTPService
from src.config import get_sftp_config
from src.utils.logger import get_logger

logger = get_logger(__name__)

def test_conexion_sftp():
    try:
        sftp = SFTPService(get_sftp_config())
        conectado = sftp.connect()
        if conectado:
            print("Conexión SFTP exitosa")
            sftp.disconnect()
        else:
            print("Error al conectar a SFTP")
    except Exception as e:
        print(f"Error en la prueba de conexión SFTP: {e}")

if __name__ == "__main__":
    test_conexion_sftp()