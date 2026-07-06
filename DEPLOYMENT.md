# Guía de despliegue en LAN — AI World Cup 2026

Despliegue distribuido en dos equipos de la misma red local.

## Topología

```
[Dispositivos cliente] --HTTPS 443--> [SERVIDOR B "eliminatorias"]      [SERVIDOR A "servidor-a"]
   (usuario+contraseña)                 Caddy + SPA React                 backend FastAPI + ML + SQLite
                                          └── /api/* --HTTP 8000 (LAN)-->  (TODO el cómputo ocurre aquí)
```

- **Servidor A** = este equipo. Ejecuta el backend, los 4 modelos y la base de datos.
- **Servidor B** = el otro equipo ("eliminatorias"). Sirve la web y reenvía `/api` al A.
- Los clientes solo tocan el Servidor B por HTTPS (mismo origen → sin CORS, un solo certificado).

## Datos de TU red (ya descubiertos)

| Parámetro | Valor |
|-----------|-------|
| Servidor A · hostname | `servidor-a` |
| Servidor A · IP LAN | **`192.168.1.50`** |
| Servidor A · puerto backend | `8000` |
| Servidor B · IP LAN | _(rellena la IP del equipo "eliminatorias")_ |

> Ignora las IP `192.168.56.1` y `172.26.160.1` del Servidor A: son adaptadores virtuales (VirtualBox/Hyper-V), no la LAN real.

---

## Parte 1 — Servidor A (este equipo)

### 1.1 Configuración
`.env` ya tiene `SERVIDOR_A_IP=192.168.1.50`. **Antes de producción**, cambia `SECRET_KEY` y `ADMIN_PASSWORD`.

### 1.2 Entrenar los modelos (una vez)
```powershell
.\.venv\Scripts\python.exe -m ml.train --bayes   # Elo + XGBoost + NN + Bayesiano
```

### 1.3 Arrancar el backend en la LAN  (RECOMENDADO: nativo)
El venv ya tiene todas las dependencias y los artefactos → soporta los **4 modelos**.
```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```
> Clave: `--host 0.0.0.0` (escucha en la LAN, no solo localhost).
>
> *Alternativa Docker* (solo Elo salvo que extiendas la imagen con xgboost+torch):
> `docker compose -f deploy/docker-compose.backend.yml up -d --build`

Para dejarlo corriendo de forma permanente (servicio Windows), puedes usar **NSSM** o el
Programador de tareas; opcional para una demo.

### 1.4 Abrir el firewall de Windows  (PowerShell **como administrador**)
```powershell
New-NetFirewallRule -DisplayName "WC2026 backend 8000" -Direction Inbound `
  -Action Allow -Protocol TCP -LocalPort 8000 -RemoteAddress LocalSubnet
```
`-RemoteAddress LocalSubnet` limita el acceso a tu red local. Para máxima seguridad,
sustitúyelo por la IP exacta del Servidor B: `-RemoteAddress 192.168.1.XX`.

### 1.5 Verificar localmente
```powershell
Invoke-RestMethod http://localhost:8000/api/health   # -> status: ok
```

---

## Parte 2 — Servidor B ("eliminatorias")

> Si tienes una sesión de Claude Code abierta en el Servidor B, pásale el archivo
> [`deploy/PROMPT-SERVIDOR-B.md`](deploy/PROMPT-SERVIDOR-B.md) (cópialo como primer mensaje).

### 2.1 Requisitos
- Docker + Docker Compose.
- Una copia del repositorio (git clone, o copia por carpeta compartida de la LAN).

### 2.2 Probar la conexión con el Servidor A  (antes de nada)
```bash
curl http://192.168.1.50:8000/api/health      # debe devolver {"status":"ok",...}
# o, si tienes Python:  python scripts/check_backend.py 192.168.1.50
```
Si falla: revisa que el backend de A esté arrancado con `--host 0.0.0.0` y que el
firewall de A permita el 8000 (Parte 1.4).

### 2.3 Configurar `.env` en el Servidor B
```
SERVIDOR_A_IP=192.168.1.50
SERVIDOR_A_PORT=8000
```

### 2.4 Construir y levantar el frontend (Caddy + SPA)
```bash
docker compose -f deploy/docker-compose.frontend.yml up -d --build
```
Esto compila la app React y la sirve con Caddy en el puerto 443, reenviando `/api` al A.

### 2.5 Certificado HTTPS de confianza en los clientes
Caddy usa su CA interna. Expórtala e instálala en cada dispositivo cliente:
```bash
docker compose -f deploy/docker-compose.frontend.yml exec frontend \
  cat /data/caddy/pki/authorities/local/root.crt > caddy-root.crt
```
Instala `caddy-root.crt` como **CA raíz de confianza** en los navegadores/dispositivos de la LAN.

---

## Parte 3 — Verificación end-to-end

Desde un **tercer dispositivo** de la LAN:
1. Abre `https://<IP-del-Servidor-B>` → pantalla de login.
2. Entra con `admin` / (tu `ADMIN_PASSWORD`).
3. Mira el Dashboard, cambia de modelo, registra un resultado en *Partidos*.
4. En la terminal del **Servidor A** verás las peticiones llegando (`GET /api/...`) → confirma que el cómputo ocurre en A.

---

## Seguridad (checklist)

- [ ] `SECRET_KEY` y `ADMIN_PASSWORD` cambiados en `.env` (ambos servidores donde aplique).
- [ ] Firewall del A: 8000 solo desde la LAN (o solo desde la IP del B).
- [ ] B expone únicamente el 443.
- [ ] CA de Caddy instalada en los clientes (HTTPS sin avisos).
- [ ] Perfiles y cupos configurados en el panel Admin.

## Modelos en el backend desplegado

- **Nativo (recomendado):** los 4 modelos (Elo/XGBoost/NN/Bayesiano).
- **Docker:** por defecto solo Elo. Para los 4, monta `ml/artifacts` (ya configurado en el
  compose) **y** añade `xgboost` + `torch` a `backend/requirements.txt` de la imagen.

## Eliminatorias (knockouts)

**Materialización automática:** al registrar el último resultado de la fase de grupos (los 72
partidos), la app **deriva la Ronda de 32 del bracket oficial** con los equipos reales
(`backend/app/services/knockouts.py` + `ml/simulation/bracket.py`) y la crea como partidos
concretos. A medida que registras resultados de cada ronda, se materializan octavos →
cuartos → semis → final. Los empates en eliminatorias piden el ganador por penaltis. No
depende de la API; con una fuente configurada (`FOOTBALL_DATA_ORG_TOKEN`, gratis) el sync también dispara la materialización.
