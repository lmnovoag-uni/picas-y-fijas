# Picas y Fijas (versión distribuida)

API REST con JSON (Flask), datos en memoria, front básico en `/` y despliegue en Kubernetes.

## Endpoints
Todos, salvo `/login`, requieren `Authorization: Bearer <token>`.

| Método | Ruta | Cuerpo | Descripción |
| --- | --- | --- | --- |
| POST | `/login` | `{"nombre":"ana"}` | Registra el nombre del jugador y devuelve el token firmado |
| POST | `/juego` | `{"numero":"4271"}` | Crea un juego (estado `sin_completar`) |
| GET | `/juego` | | Lista juegos: id, creador, estado, jugadores, ganador |
| GET | `/juego/{id}` | | Estado, turno, ganador e historial de jugadas |
| PUT | `/juego/{id}` | `{"nombre":"beto","numero":"9876"}` | Se une; el juego pasa a `en_juego` y el primer turno es aleatorio |
| POST | `/juego/{id}/jugar` | `{"numero":"1234"}` | Intento contra el número del rival; solo en tu turno |

Estados: `sin_completar`, `en_juego`, `terminado`. Gana quien obtiene 4 fijas.
Validación del número: solo dígitos, 4 dígitos, sin repetidos (si no, HTTP 400).

## Ejecutar local
```bash
pip install -r requirements.txt
flask --app app run --port 5000
```

## Desplegar en Killercoda
1. En el Playground de Kubernetes:
```bash
git clone https://github.com/TU_USUARIO/TU_REPO.git && cd TU_REPO
kubectl apply -f killercoda/namespace.yaml
kubectl -n picas-y-fijas create secret generic picas-auth --from-literal=signing-key="$(openssl rand -hex 32)"
kubectl apply -f killercoda/deployment.yaml -f killercoda/service.yaml
kubectl -n picas-y-fijas rollout status deployment/picas-y-fijas --timeout=300s
kubectl port-forward -n picas-y-fijas service/picas-y-fijas --address 0.0.0.0 8080:80
```
3. En **Traffic / Ports** abre el puerto `8080`. Usa dos pestañas con nombres distintos.

Nota: los errores se devuelven siempre como JSON (`{"error": ...}`). Si reinicias el Pod, los jugadores registrados se pierden y hay que iniciar sesión de nuevo. Se usa una réplica y un worker porque los juegos están en memoria; reiniciar el Pod los borra.
