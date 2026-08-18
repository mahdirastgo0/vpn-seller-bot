from __future__ import annotations

import json
import time
import uuid
from urllib.parse import quote

import httpx

from app.config import PanelConfig


class SanaeiApiError(Exception):
    pass


class SanaeiClient:
    def __init__(self, panel: PanelConfig):
        self.panel = panel

        self._client = httpx.AsyncClient(
            verify=False,
            timeout=30,
            headers={
                "Authorization": f"Bearer {panel.api_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs,
    ) -> dict:

        url = self.panel.url.rstrip("/") + endpoint

        try:
            response = await self._client.request(
                method,
                url,
                **kwargs,
            )

            print(
                f"[SANAEI] {method} {endpoint} -> "
                f"{response.status_code}"
            )

            response.raise_for_status()

        except httpx.HTTPStatusError as e:
            raise SanaeiApiError(
                f"HTTP {e.response.status_code} "
                f"from {endpoint}: {e.response.text}"
            ) from e

        except httpx.HTTPError as e:
            raise SanaeiApiError(
                f"HTTP error while calling {endpoint}: {e}"
            ) from e

        try:
            data = response.json()
        except Exception as e:
            raise SanaeiApiError(
                f"Invalid JSON response from {endpoint}: "
                f"{response.text[:1000]}"
            ) from e

        if not isinstance(data, dict):
            raise SanaeiApiError(
                f"Unexpected response from {endpoint}: {data!r}"
            )

        if data.get("success") is False:
            raise SanaeiApiError(
                data.get("msg")
                or f"Sanaei API returned success=false from {endpoint}"
            )

        return data

    async def get_inbounds(self) -> list[dict]:

        data = await self._request(
            "GET",
            "/panel/api/inbounds/list",
        )

        obj = data.get("obj")

        if not isinstance(obj, list):
            return []

        return obj

    async def get_inbound(
        self,
        inbound_id: int,
    ) -> dict | None:

        inbounds = await self.get_inbounds()

        for inbound in inbounds:
            try:
                if int(inbound.get("id")) == int(inbound_id):
                    return inbound
            except (TypeError, ValueError):
                continue

        return None

    async def add_client(
        self,
        email: str,
        traffic_gb: int,
        duration_days: int,
        inbound_id: int | None = None,
        client_uuid: str | None = None,
    ) -> dict:

        if inbound_id is None:
            inbound_id = self.panel.inbound_id

        if client_uuid is None:
            client_uuid = str(uuid.uuid4())

        total_gb = int(traffic_gb)

        # 0 means unlimited in Sanaei/X-UI
        if total_gb > 0:
            total_bytes = total_gb * 1024 * 1024 * 1024
        else:
            total_bytes = 0

        # expiryTime is milliseconds
        if duration_days > 0:
            expiry_time = int(
                (time.time() + duration_days * 24 * 60 * 60) * 1000
            )
        else:
            expiry_time = 0

        payload = {
            "inboundIds": [
                int(inbound_id)
            ],
            "client": {
                "email": email,
                "uuid": client_uuid,
                "enable": True,
                "totalGB": total_bytes,
                "expiryTime": expiry_time,
            },
        }

        print()
        print("=" * 60)
        print("SANAEI CREATE CLIENT")
        print("PANEL:", self.panel.name)
        print("INBOUND:", inbound_id)
        print("EMAIL:", email)
        print("UUID:", client_uuid)
        print("TRAFFIC:", traffic_gb, "GB")
        print("DURATION:", duration_days, "days")
        print("ENDPOINT:", "/panel/api/clients/add")
        print("PAYLOAD:")
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        print("=" * 60)

        await self._request(
            "POST",
            "/panel/api/clients/add",
            json=payload,
        )

        # بعد از ساخت کلاینت، اطلاعات inbound را دوباره می‌گیریم
        # تا port / protocol / streamSettings واقعی را داشته باشیم.
        inbound = await self.get_inbound(inbound_id)

        if inbound is None:
            raise SanaeiApiError(
                f"اینباند {inbound_id} روی پنل پیدا نشد."
            )

        return {
            "client_uuid": client_uuid,
            "email": email,
            "inbound": inbound,
        }

    async def get_client_traffic(
        self,
        email: str,
    ) -> dict | None:

        data = await self._request(
            "GET",
            f"/panel/api/inbounds/getClientTraffics/{quote(email)}",
        )

        return data.get("obj")

    async def delete_client(
        self,
        inbound_id: int,
        client_uuid: str,
    ) -> None:

        await self._request(
            "POST",
            f"/panel/api/inbounds/{inbound_id}/delClient/{client_uuid}",
        )

    async def close(self) -> None:
        await self._client.aclose()


def build_config_link(
    panel: PanelConfig,
    inbound: dict,
    client_uuid: str,
    email: str,
) -> str:

    # ---------------------------------------------------------
    # streamSettings ممکن است از API به صورت dict یا JSON string
    # برگردد. هر دو حالت را پشتیبانی می‌کنیم.
    # ---------------------------------------------------------

    raw_stream_settings = inbound.get("streamSettings") or {}

    if isinstance(raw_stream_settings, str):
        try:
            stream_settings = json.loads(
                raw_stream_settings or "{}"
            )
        except json.JSONDecodeError:
            stream_settings = {}
    elif isinstance(raw_stream_settings, dict):
        stream_settings = raw_stream_settings
    else:
        stream_settings = {}

    # ---------------------------------------------------------
    # اطلاعات اصلی inbound
    # ---------------------------------------------------------

    network = str(
        stream_settings.get("network", "tcp")
    )

    security = str(
        stream_settings.get("security", "none")
    )

    port = inbound.get("port")

    if not port:
        raise SanaeiApiError(
            "Inbound port پیدا نشد."
        )

    protocol = str(
        inbound.get("protocol")
        or panel.protocol
        or "vless"
    ).lower()

    # فعلاً فقط VLESS را پشتیبانی می‌کنیم.
    if protocol != "vless":
        raise SanaeiApiError(
            f"Protocol فعلی {protocol} است؛ "
            f"ساخت لینک فقط برای VLESS پیاده‌سازی شده."
        )

    # ---------------------------------------------------------
    # TLS
    # ---------------------------------------------------------

    tls_settings = (
        stream_settings.get("tlsSettings")
        or {}
    )

    server_name = (
        tls_settings.get("serverName")
    )

    if not server_name:
        names = (
            tls_settings.get("serverNames")
            or []
        )

        if names:
            server_name = names[0]

    if not server_name:
        server_name = (
            panel.url
            .split("://")[-1]
            .split(":")[0]
            .split("/")[0]
        )

    # ---------------------------------------------------------
    # XHTTP settings
    # ---------------------------------------------------------

    xhttp_settings = (
        stream_settings.get("xhttpSettings")
        or {}
    )

    path = xhttp_settings.get("path")

    host = xhttp_settings.get("host")

    mode = xhttp_settings.get("mode")

    # ---------------------------------------------------------
    # Query parameters
    # ---------------------------------------------------------

    params: list[str] = [
        f"type={quote(network)}",
        f"security={quote(security)}",
    ]

    # ---------------------------------------------------------
    # TLS
    # ---------------------------------------------------------

    if security == "tls":

        params.append(
            "sni=" + quote(str(server_name))
        )

    # ---------------------------------------------------------
    # XHTTP
    # ---------------------------------------------------------

    if network == "xhttp":

        if path:
            params.append(
                "path=" + quote(str(path))
            )

        if host:
            params.append(
                "host=" + quote(str(host))
            )

        if mode:
            params.append(
                "mode=" + quote(str(mode))
            )

    # ---------------------------------------------------------
    # WebSocket
    # ---------------------------------------------------------

    elif network == "ws":

        ws_settings = (
            stream_settings.get("wsSettings")
            or {}
        )

        ws_path = ws_settings.get("path")

        ws_headers = (
            ws_settings.get("headers")
            or {}
        )

        if ws_path:
            params.append(
                "path=" + quote(str(ws_path))
            )

        if ws_headers.get("Host"):
            params.append(
                "host=" + quote(
                    str(ws_headers["Host"])
                )
            )

    # ---------------------------------------------------------
    # gRPC
    # ---------------------------------------------------------

    elif network == "grpc":

        grpc_settings = (
            stream_settings.get("grpcSettings")
            or {}
        )

        service_name = (
            grpc_settings.get("serviceName")
        )

        if service_name:
            params.append(
                "serviceName=" + quote(
                    str(service_name)
                )
            )

    # ---------------------------------------------------------
    # Fragment / display name
    # ---------------------------------------------------------

    fragment = quote(
        email,
        safe="",
    )

    # ---------------------------------------------------------
    # VLESS URL
    # ---------------------------------------------------------

    link = (
        f"vless://{client_uuid}"
        f"@{server_name}:{port}"
        f"?{'&'.join(params)}"
        f"#{fragment}"
    )

    return link