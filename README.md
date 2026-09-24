# Newsletter Digest Agent

Agente que cada mañana revisa tu Gmail, encuentra los correos de newsletter
nuevos, los sintetiza con Gemini, y te manda un resumen consolidado como
correo nuevo. Corre solo, todos los días, en GitHub Actions (gratis).

## Configuración (una sola vez)

### 1. Contraseña de aplicación de Gmail
1. Activa la verificación en dos pasos en tu cuenta de Google (si no la tienes).
2. Ve a https://myaccount.google.com/apppasswords
3. Genera una "contraseña de aplicación" (16 caracteres, sin espacios al copiarla).
   Guárdala, la vas a necesitar como secreto `GMAIL_APP_PASSWORD`.

### 2. API key de Gemini (gratis)
1. Ve a https://aistudio.google.com/apikey
2. Crea una API key y guárdala como secreto `GEMINI_API_KEY`.

### 3. Sube este proyecto a un repo de GitHub
```bash
cd newsletter-agent
git init
git add .
git commit -m "Newsletter digest agent"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/newsletter-agent.git
git push -u origin main
```

### 4. Configura los secretos del repo
En GitHub: **Settings → Secrets and variables → Actions → New repository secret**

| Nombre | Valor |
|---|---|
| `GMAIL_ADDRESS` | tu correo de Gmail |
| `GMAIL_APP_PASSWORD` | la contraseña de aplicación del paso 1 |
| `GEMINI_API_KEY` | la API key del paso 2 |

(Opcional) agrega `DIGEST_TO_EMAIL` si quieres que el resumen llegue a un
correo distinto al de Gmail (por defecto se manda a ti mismo).

### 5. Prueba manual
Ve a la pestaña **Actions** de tu repo → selecciona "Newsletter Digest Agent"
→ **Run workflow**. Revisa los logs y tu bandeja de entrada.

### 6. Listo
El workflow ya está programado para correr todos los días (ajusta la hora
en `.github/workflows/newsletter-digest.yml` según tu zona horaria).

## Para tu descripción técnica (1 página)

- **Tarea**: sintetizar newsletters de correo automáticamente cada día.
- **Por qué un agente**: requiere leer múltiples correos, filtrar, recordar
  cuáles ya se procesaron (estado persistente en `state.json`), decidir qué
  incluir, sintetizar con un modelo, y verificar la entrega — no es un solo
  prompt-respuesta.
- **Tecnologías**: modelo Gemini 2.0 Flash (gratis), Python puro como
  "harness" (sin framework externo), herramientas = IMAP (leer) y SMTP
  (enviar), estado = archivo JSON versionado en el repo, entorno de
  despliegue = GitHub Actions (cron diario, gratis).
- **Flujo de ejecución**: cron dispara el workflow → agente se autentica en
  Gmail → filtra correos nuevos no procesados → llama a Gemini para
  sintetizar → envía el correo con el resumen → actualiza y hace commit del
  estado.
- **Limitación / mejora futura**: el filtro de "es newsletter" es una
  heurística simple (headers + palabras clave en el remitente); podría
  fallar con newsletters que no usan `List-Unsubscribe`, o clasificar mal
  un correo normal. Una mejora sería pedirle al propio modelo que clasifique
  cada correo, o dejar que el usuario corrija manualmente y el agente
  aprenda de esas correcciones.
