# SAFE-ELEC API v1 — Non-breaking implementation plan

Status: partial implementation on an isolated branch. Three device-facing API v1 routes have been added to main.py. No database rows/schema, firmware, or deployment have been changed.

## 1. Confirmed current state

- The active Render entry point is `gunicorn ... main:app`; `main.py` is the backend to extend.
- Existing firmware compatibility routes are `GET /api/config`, `GET /api/command`, and `POST /api/data`. Keep them operational during migration.
- `iot_core_projects`, `iot_core_devices`, `iot_core_telemetry`, and `iot_core_commands` already exist.
- `iot_core_devices` already has `device_type`, `hardware_model`, `firmware_version`, `token_hash`, `capabilities`, `metadata`, `last_seen_at`, and status fields.
- The SAFE-ELEC project key currently resolves through `IOT_PROJECT_KEY=safe-elec-v4-2`.
- Runtime registry sync currently loads a single REST response (no explicit pagination), merges rows into an in-memory list, and does not remove stale entries.
- `DEVICE_LIST` and `relay_state` still contain the two original device IDs. A new device can appear in the in-memory registry but does not automatically receive relay command state.
- `/api/config` and legacy `/api/command` currently allow unauthenticated GET requests for firmware compatibility. Do not broaden this exception to new routes.
- The Meter/Water/Electricity web page is a separate application. Its `loadElectricFromESP()` and `loadWaterFromESP()` functions are placeholders and currently display “not connected”; they are not SAFE-ELEC firmware endpoints.

## 2. API v1 contract (SAFE-ELEC only)

All new device endpoints require `X-Device-Token`. All new administrative provisioning endpoints require a separate server-side `SAFE_ELEC_PROVISIONING_TOKEN`. Never place either secret in browser code or public repository files.

| Method | Route | Purpose | Authentication | Status |
|---|---|---|---|
| POST | `/api/v1/safe-elec/devices/register` | Provision a device; issue a token once | Provisioning token | **Implemented on branch** |
| POST | `/api/v1/safe-elec/devices/heartbeat` | Update online/firmware/capability status | Device token | **Implemented on branch** |
| POST | `/api/v1/safe-elec/telemetry` | Store versioned telemetry | Device token | **Implemented on branch** |
| GET | `/api/v1/safe-elec/config` | Fetch device configuration | Device token |
| GET | `/api/v1/safe-elec/devices` | List registered devices, paginated | Dashboard session |
| GET | `/api/v1/safe-elec/readings` | Read paginated telemetry for one device | Dashboard session |
| POST | `/api/v1/safe-elec/commands` | Queue a command | Dashboard session |
| GET | `/api/v1/safe-elec/devices/commands` | Poll pending commands | Device token |
| POST | `/api/v1/safe-elec/devices/commands/ack` | Acknowledge command result | Device token |

Response conventions: JSON; `ok`; stable machine-readable `error`; `schema_version`; timestamps in ISO-8601 UTC. List endpoints use cursor or bounded page/limit (default 50, maximum 200). Never return token hashes.


### Implemented route behavior (branch only)

- Registration requires the Render-only `SAFE_ELEC_PROVISIONING_TOKEN` via `X-Provisioning-Token`; it validates the project is active, enforces the existing `(project_id, device_key)` unique constraint, stores only SHA-256 token hash, and returns the raw token once.
- Heartbeat and telemetry use `X-Device-Token` through the existing token validator. Disabled/revoked devices are rejected.
- Telemetry writes the provided `schema_version` to the matching database column, not into the payload object.
- The existing DB already has the unique device key constraint and indexes for device/status and telemetry time queries. Do not add duplicate indexes without query-plan evidence.
- RLS currently provides owner-scoped SELECT policies for projects/devices/telemetry/commands and owner-scoped command INSERT. Device and telemetry writes from these routes use the Render service-role key only; never expose it to a client.
- No automated tests or Actions workflow runs were found for the latest branch commit. These routes have not yet been runtime-tested against a staging project.

## 2A. Versioned telemetry measurement contract

The device telemetry route accepts legacy schema v1 unchanged. Schema v2 requires a top-level `payload.measurements` object. Each metric is keyed by a stable machine name and contains:

```json
{
  "schema_version": 2,
  "device_id": "DEVICE-KEY",
  "observed_at": "2026-11-19T07:00:00Z",
  "payload": {
    "measurements": {
      "voltage_l1_n": {
        "value": 230.4,
        "unit": "V",
        "quality": "valid",
        "accuracy": 1.0,
        "sensor_status": "installed",
        "observed_at": "2026-11-19T07:00:00Z",
        "calibrated_at": "2026-01-01T00:00:00Z",
        "sensor": {
          "model": "meter-model",
          "measurement_method": "true_rms"
        }
      },
      "earth_resistance": {
        "value": null,
        "unit": "ohm",
        "quality": "not_installed",
        "sensor_status": "not_installed"
      }
    },
    "device": {
      "firmware_version": "1.0.0",
      "uptime_seconds": 86400,
      "free_heap_bytes": 120000,
      "wifi_rssi_dbm": -58
    }
  }
}
```

Allowed quality states: `valid`, `not_installed`, `no_data`, `sensor_fault`, `out_of_range`, `uncalibrated`, and `estimated`. Only `valid` measurements may carry a numeric value; other states must use JSON null. Units are mandatory. Accuracy, sensor identity/model, measurement method, observation timestamp and calibration timestamp are optional metadata fields. The API validates structure and types; it does not certify sensor accuracy, calibration, electrical safety, or IEC conformity.

Suggested metric families (send only what the installed hardware can actually measure):
- AC electrical: phase-neutral and phase-phase voltage, phase/neutral current, active/reactive/apparent power, power factor, frequency, import/export energy and demand.
- Power quality: dips, swells, interruptions, voltage/current unbalance, harmonics/THD, flicker and rapid voltage changes, only with suitable metering hardware and sampling.
- Protection/safety: PE continuity, earth resistance, insulation resistance, leakage current, RCD/RCBO and breaker state, phase sequence/loss, SPD status and arc-fault indication, only with dedicated rated instruments/sensors.
- Environment: panel/terminal temperature, humidity, smoke/gas, water ingress, enclosure door and vibration.
- Device health: uptime, free heap, supply status, RSSI, restart count, firmware version, sensor health, heartbeat and failover state.

Site nominal voltage and alarm thresholds must be configured for the installation and instrument. Do not treat 220/380 V or 230/400 V as universal thresholds. IEC-aligned monitoring requires suitable calibrated instruments and measurement methods; this API alone is not an IEC certification.

The branch implementation rejects oversized v1/v2 requests and validates v2 measurement names, units, quality/value combinations, accuracy types, sensor metadata and timestamps before persistence. Existing v1 payloads and legacy `POST /api/data` are retained for migration compatibility. Dashboard mapping of v2 measurement payloads, firmware implementation, hardware-specific acquisition and runtime tests remain separate rollout work.

## 3. Registry and scale requirements

- Database registry is authoritative; do not hardcode a maximum number of devices.
- Every device belongs to the resolved SAFE-ELEC project ID. All database queries must filter by that project ID.
- Device identity is the unique pair `(project_id, device_key)`.
- Store type/model, role, firmware version, schema version, site/zone metadata, and JSON capabilities.
- Registry synchronization must use PostgREST range pagination and only replace registry state after a complete successful fetch. A failed/partial fetch must not erase already loaded devices.
- Preserve live telemetry and UI-only fields when refreshing registry metadata.
- Initialize command state by registered device ID/capabilities; never assume every device has six relay zones.
- Use database-backed commands for new devices. Keep the legacy in-memory relay adapter only for the existing firmware until its migration is separately tested.

## 4. Database hardening required before production rollout

The existing tables are present, but their full constraints, indexes, and RLS definitions must be reviewed before applying changes. Proposed additive migration (not yet applied):

1. Confirm/ensure unique constraint on `iot_core_devices(project_id, device_key)`.
2. Add an optional per-device sequence/idempotency field to telemetry and a unique index scoped by project and device, after confirming firmware payload compatibility.
3. Add indexes for telemetry lookup `(project_id, device_id, observed_at DESC)` and command polling `(project_id, device_id, status, created_at)`.
4. Verify RLS policies prevent cross-project reads/writes. Server-side service-role access must remain on Render only.
5. Do not alter `dorm_rooms`, `electricity`, `water`, or `bills`; do not reuse legacy `devices`, `device_state`, or `device_pairs` without a separate dependency review.
6. Do not invent or insert an `owner_user_id`. Use the already existing SAFE-ELEC project record and its verified owner reference.

## 5. Safe rollout order

1. Add unit tests for token validation, project scoping, pagination, malformed payloads, and unknown/disabled devices.
2. Add API v1 routes as additive adapters; keep legacy route response shapes unchanged.
3. Test with a simulated third device in a non-production test project/database. Verify wrong token is rejected, correct token is accepted, and another project cannot read/write its data.
4. Test dashboard discovery and command behavior for devices with different capabilities (including no relay capability).
5. Deploy only after test evidence and environment variables are verified. Do not flash or rewire the current MASTER/BACKUP pair as part of this server-only stage.
6. Migrate the physical pair to API v1 only in a later, separately approved firmware release.

## 6. Separate Meter IoT application

The meter app must retain its own URL and its existing room, electricity, water, and bill data. It must not call SAFE-ELEC routes or share SAFE-ELEC device tokens. Its ESP ingestion API should be a separately named service/function and its own table namespace (for example `meter_iot_devices`, `meter_iot_readings`). No meter endpoint is implemented by this SAFE-ELEC plan.

## 7. Release gate

This branch is not production-ready until Python syntax/import checks, route-level tests (including invalid/missing tokens), duplicate registration tests, a simulated third-device test, and staging persistence checks pass. No production deployment is authorized by this document.
