# EP100 Web Configurator

Aplicacion web local para leer y configurar EP100/EP1XX por RS485 usando los comandos JSON observados en EPTools.

## Uso

1. Conecta el EP100 al PC con un adaptador USB-RS485.
2. Alimenta el EP100 con 9-36 VDC.
3. Sirve esta carpeta en localhost.
4. Abre Chrome o Edge y conecta el puerto serial.

Comando recomendado:

```powershell
cd ep100-web
python server.py
```

Luego abre:

```text
http://localhost:5173
```

## Comandos implementados

- `getSystemInfo`
- `setSystemInfo`
- `getUartInfo`
- `setUartInfo`
- `getSocketInfo`
- `setSocketInfo`
- Consola JSON manual para comandos adicionales.

El puerto TCP por defecto para datos seriales es `4000`.

## Notas

- Web Serial solo funciona en navegadores compatibles y contexto seguro. `localhost` es valido.
- El EP100 probado responde por RS485 en `9600 8N1`, porque su UART fue configurado asi.
- EPTools de fabrica suele usar `115200 8N1`; selecciona el baud correcto antes de conectar.
