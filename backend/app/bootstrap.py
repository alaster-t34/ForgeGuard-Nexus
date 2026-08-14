from datetime import datetime, timedelta, timezone

from app.domain.enums import AssetStatus, RiskLevel
from app.domain.schemas import (
    Asset,
    AuditEvent,
    InventoryItem,
    ProductionOrder,
    TechnicianProfile,
)


def seed_store(store) -> None:
    if not store.list_assets():
        assets = [
            Asset(
                id="FG-BRG-001",
                name="2号线主轴轴承",
                asset_class="rolling-element-bearing",
                line="装配2号线",
                location="M-17工位",
                status=AssetStatus.HEALTHY,
                health_score=94.0,
                estimated_rul_hours=690.0,
                criticality=RiskLevel.HIGH,
                tags=["bearing", "spindle", "critical-path"],
                manufacturer="SKF",
                model="6205-2RS-C3",
                serial_number="M17-6205-2026-02",
                energy_baseline_kw=11.8,
                mtbf_hours=7200,
            ),
            Asset(
                id="FG-PUMP-004",
                name="冷却液循环泵",
                asset_class="centrifugal-pump",
                line="机加工4号单元",
                location="U-3公用工程区",
                status=AssetStatus.WATCH,
                health_score=81.0,
                estimated_rul_hours=1180.0,
                criticality=RiskLevel.MEDIUM,
                tags=["pump", "motor", "coolant"],
                manufacturer="Grundfos",
                model="CR-15",
                energy_baseline_kw=7.6,
                mtbf_hours=9100,
            ),
            Asset(
                id="FG-FAN-008",
                name="排风机驱动端轴承",
                asset_class="fan-bearing",
                line="表面处理线",
                location="R-2屋面区",
                status=AssetStatus.HEALTHY,
                health_score=97.0,
                estimated_rul_hours=2140.0,
                criticality=RiskLevel.LOW,
                tags=["fan", "bearing", "hvac"],
                manufacturer="ABB",
                model="M3BP-160",
                energy_baseline_kw=5.4,
                mtbf_hours=12000,
            ),
            Asset(
                id="FG-GBX-012",
                name="传送齿轮箱",
                asset_class="gearbox",
                line="装配1号线",
                location="T-04工位",
                status=AssetStatus.WARNING,
                health_score=69.0,
                estimated_rul_hours=310.0,
                criticality=RiskLevel.HIGH,
                tags=["gearbox", "transfer", "critical-path"],
                manufacturer="SEW-Eurodrive",
                model="R77",
                energy_baseline_kw=14.5,
                mtbf_hours=8400,
            ),
            Asset(
                id="FG-CMP-021",
                name="压缩空气机组",
                asset_class="compressor",
                line="公用工程",
                location="C-1空压机房",
                status=AssetStatus.HEALTHY,
                health_score=91.0,
                estimated_rul_hours=1660.0,
                criticality=RiskLevel.MEDIUM,
                tags=["compressor", "air", "utilities"],
                manufacturer="Atlas Copco",
                model="GA18",
                energy_baseline_kw=18.2,
                mtbf_hours=9800,
            ),
        ]
        for asset in assets:
            store.upsert_asset(asset)

    if not store.list_inventory():
        inventory = [
            InventoryItem(
                id="6205-2RS-C3 bearing",
                name="6205-2RS-C3 精密轴承",
                quantity_on_hand=6,
                quantity_reserved=1,
                reorder_point=3,
                supplier="SKF 授权经销商",
                lead_time_days=2,
                unit_cost=280.0,
                circularity="recyclable",
            ),
            InventoryItem(
                id="approved grease cartridge",
                name="食品级高速轴承润滑脂",
                quantity_on_hand=14,
                quantity_reserved=2,
                reorder_point=4,
                supplier="Klüber Lubrication",
                lead_time_days=1,
                unit_cost=78.0,
                circularity="consumable",
            ),
            InventoryItem(
                id="locking washer",
                name="KM5 锁紧垫圈",
                quantity_on_hand=21,
                quantity_reserved=0,
                reorder_point=5,
                supplier="本地 MRO 供应中心",
                lead_time_days=1,
                unit_cost=12.0,
                circularity="recyclable",
            ),
            InventoryItem(
                id="laser alignment kit",
                name="便携式轴系对中仪",
                quantity_on_hand=2,
                quantity_reserved=1,
                reorder_point=1,
                supplier="厂内工具库",
                lead_time_days=0,
                unit_cost=16800.0,
                circularity="remanufactured",
            ),
        ]
        for item in inventory:
            store.upsert_inventory(item)

    if not store.list_production():
        now = datetime.now(timezone.utc)
        orders = [
            ProductionOrder(
                id="LOT-2026-07-30-B",
                line="装配2号线",
                product="电驱壳体",
                quantity=420,
                completed_quantity=286,
                due_at=now + timedelta(hours=8),
                safe_transition_minutes=24,
                downstream_buffer_minutes=35,
                priority=RiskLevel.HIGH,
                status="running",
            ),
            ProductionOrder(
                id="LOT-2026-07-30-C",
                line="机加工4号单元",
                product="冷却液歧管",
                quantity=240,
                completed_quantity=150,
                due_at=now + timedelta(hours=12),
                safe_transition_minutes=18,
                downstream_buffer_minutes=42,
                priority=RiskLevel.MEDIUM,
                status="running",
            ),
        ]
        for order in orders:
            store.upsert_production(order)

    if not store.list_technicians():
        technicians = [
            TechnicianProfile(
                id="TECH-001",
                name="张睿",
                team="机械可靠性 A 组",
                skills=["mechanical maintenance", "vibration verification", "bearing replacement"],
                certifications=["LOTO authorization", "precision alignment"],
                shift="A",
                available=True,
                fatigue_risk=RiskLevel.LOW,
            ),
            TechnicianProfile(
                id="TECH-002",
                name="李文",
                team="机械可靠性 A 组",
                skills=["condition monitoring", "thermography", "ultrasound"],
                certifications=["CAT II vibration analyst", "LOTO authorization"],
                shift="A",
                available=True,
                fatigue_risk=RiskLevel.LOW,
            ),
            TechnicianProfile(
                id="TECH-003",
                name="陈宇",
                team="电气可靠性 B 组",
                skills=["electrical maintenance", "motor diagnostics"],
                certifications=["electrical isolation", "LOTO authorization"],
                shift="B",
                available=False,
                fatigue_risk=RiskLevel.MEDIUM,
                active_work_orders=2,
            ),
        ]
        for technician in technicians:
            store.upsert_technician(technician)

    if not store.list_audit(limit=1):
        store.append_audit(
            AuditEvent(
                category="system",
                actor="ForgeGuard Bootstrap",
                action="seeded_demo_environment",
                object_id="platform",
                detail="工业 5.0 跨平台演示数据已初始化。",
            )
        )
