from pathlib import Path

p = Path("app/database/crud.py")
s = p.read_text()

old = '''async def list_user_configs(session: AsyncSession, user_id: int) -> list[VpnConfig]:
    result = await session.execute(
        select(VpnConfig).where(VpnConfig.user_id == user_id).order_by(VpnConfig.created_at.desc())
    )
    return list(result.scalars().all())
'''

new = '''async def list_user_configs(session: AsyncSession, user_id: int) -> list[VpnConfig]:
    result = await session.execute(
        select(VpnConfig)
        .where(VpnConfig.user_id == user_id)
        .order_by(VpnConfig.created_at.desc())
    )
    return list(result.scalars().all())


async def get_user_config(
    session: AsyncSession,
    config_id: int,
    user_id: int,
) -> VpnConfig | None:
    result = await session.execute(
        select(VpnConfig).where(
            VpnConfig.id == config_id,
            VpnConfig.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def update_vpn_config_link(
    session: AsyncSession,
    config: VpnConfig,
    config_link: str,
) -> VpnConfig:
    config.config_link = config_link
    await session.commit()
    await session.refresh(config)
    return config
'''

if old not in s:
    raise SystemExit("TARGET BLOCK NOT FOUND IN crud.py")

p.write_text(s.replace(old, new))