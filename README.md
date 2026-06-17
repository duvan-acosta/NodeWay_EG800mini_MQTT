# NodeWay EG800K

Firmware QuecPython y herramientas web para el modem NodeWay basado en Quectel EG800K-LA.

## Contenido

- `usr/`: archivos listos para cargar en `/usr` del EG800K. En la version validada 2026-05-21 `app_main.py` queda en texto porque el `app_main.mpy` generado en este PC no expuso `main()` en el EG800K.
- `firmware-src/`: fuentes usadas para mantenimiento y recompilacion de los `.mpy`.
- `configurator-web/`: aplicacion web local para lectura y configuracion por USB/AT/serial.
- `releases/NodeWay_EG800K_usr_firmware_2026-05-21.zip`: paquete comprimido del firmware `/usr` actualmente validado.

## Estado validado

- Seleccion de SIM externa por `GPIO28`.
- Lectura SIM externa e ICCID.
- Registro LTE y PDP con IP asignada.
- Servidor web embebido en puerto `8080` con autenticacion por sesion.
- Interfaz USB local RNDIS con DHCP; acceso local validado en `http://192.168.0.1:8080/`.
- Puente TCP solo para RS485 en puerto `5000`.
- Configuracion RS485 desde la interfaz.
- Reinicio programado funcional.
- Politica de reinicio: mantenimiento programado + recuperacion por fallo de red.
- Operador de red resuelto por `net.getNetMode()` / `AT+COPS?` cuando `net.operatorName()` devuelve `-1`.
- LEDs de estado: `GPIO36` como STATUS heartbeat y `GPIO29` como NET_STATUS.
- Validacion anti-IP stale: la IP PDP solo se considera valida si el modulo esta registrado en LTE.
- Monitor de red con reinicio de pila modem y reinicio de equipo si no recupera registro/IP.
- Telemetria MQTT periodica al broker `185.187.170.193:1883`.

## Politica de reinicio

El modem usa **dos tipos de reinicio** con objetivos distintos:

| Tipo | Default | Objetivo |
|------|---------|----------|
| **Programado** | cada 12 h | Mantenimiento preventivo |
| **Recuperacion por red** | 5 min pila / 15 min completo | Disponibilidad ante fallas o cambios LTE |

### Recuperacion por red (disponibilidad)

Si pierde registro LTE o IP valida de forma continua:

1. A los **5 min** reinicia la pila radio (`setModemFun`) y vuelve a registrar PDP.
2. Si sigue sin red, a los **15 min** hace **reinicio completo** del modem.

Esto mantiene el equipo conectado en campo ante caidas de senal, cambios de celda o IP stale.

### Reinicio programado (mantenimiento)

Independiente de la red: reinicio cada `RESTART.IntervalHours` (default 12 h) con `MinUptimeSec` minimo.

### Config

Valores en `NETWORK` del `config.json`:

```json
"StackRestartAfterNoNetworkSec": 300,
"PowerRestartAfterNoNetworkSec": 900
```

`CONFIG_VERSION: 3` restaura la recuperacion por red si una migracion anterior la deshabilito.

La politica se gestiona desde el panel web en **Politica de Reinicio**.

## Seguridad web

- Credenciales por defecto en `usr/config.json` bajo `AUTH` (`admin` / `admin`).
- Acceso local: `http://192.168.0.1:8080/login`
- Tras login exitoso se emite cookie de sesion (`HttpOnly`, 24 h).
- Rutas `/command/*`, panel principal y assets (`index.css`, `index.js`) requieren sesion valida o HTTP Basic.
- Cambiar `AUTH.User` y `AUTH.Pass` en `config.json` antes de desplegar en produccion.

## MQTT

El modem publica el estado en:

`MetaSense/ModemEGmini/<IMEI>`

El mensaje es JSON e incluye IMEI, serial, firmware, uptime, estado SIM, ICCID, IMSI, operador, registro LTE, IP PDP, modo de red, RSSI, RSRP, RSRQ, CQI, SINR y configuracion RS485.

Configuracion por defecto en `usr/config.json`:

- `MQTT.Enabled`: `true`
- `MQTT.Host`: `185.187.170.193`
- `MQTT.Port`: `1883`
- `MQTT.IntervalSec`: `300`

## Carga al modulo

Copiar el contenido de `usr/` al directorio `/usr` del EG800K por REPL/QuecPython y reiniciar el modulo.

El paquete ZIP en `releases/` contiene el mismo arbol `usr/` para distribucion o respaldo.

## Estructura protegida

`/usr/main.py` importa y ejecuta `usr.app_main.main()`.

Pendiente: recompilar `app_main.py` con el `mpy-cross` exacto compatible con el firmware `EG800KLALCR07A05M04_OCPU_QPY`. El binario generado localmente el 2026-05-21 importaba como modulo pero no exponia `main()`, por eso fue removido del paquete validado.
