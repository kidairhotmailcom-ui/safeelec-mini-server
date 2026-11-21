-- SAFE-ELEC owns its own project, credentials, telemetry and device state.
-- IoT Core remains optional and is linked only through safe_elec_iot_core_mappings.

create table if not exists public.safe_elec_projects (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null references auth.users(id),
  project_key text not null unique,
  display_name text not null,
  status text not null default 'active' check (status in ('active','paused','archived')),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
insert into public.safe_elec_projects (owner_user_id,project_key,display_name,status,metadata)
select owner_user_id,project_key,display_name,status,
       jsonb_build_object('migrated_from','iot_core_projects','source_project_id',id)
from public.iot_core_projects where project_key='safe-elec-v4-2'
on conflict (project_key) do update set display_name=excluded.display_name,status=excluded.status,updated_at=now();

create table if not exists public.safe_elec_iot_core_mappings (
  device_id text primary key references public.safe_elec_devices(device_id),
  safe_elec_project_id uuid not null references public.safe_elec_projects(id),
  iot_core_device_id uuid not null unique,
  mapping_status text not null default 'active' check (mapping_status in ('active','disabled','unlinked')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
insert into public.safe_elec_iot_core_mappings(device_id,safe_elec_project_id,iot_core_device_id)
select sd.device_id,sp.id,icd.id from public.safe_elec_devices sd
join public.iot_core_devices icd on icd.device_key=sd.device_id
join public.iot_core_projects icp on icp.id=icd.project_id and icp.project_key='safe-elec-v4-2'
join public.safe_elec_projects sp on sp.project_key='safe-elec-v4-2'
on conflict(device_id) do update set safe_elec_project_id=excluded.safe_elec_project_id,
iot_core_device_id=excluded.iot_core_device_id,mapping_status='active',updated_at=now();

create table if not exists public.safe_elec_device_credentials (
  device_id text primary key references public.safe_elec_devices(device_id),
  token_hash text not null,
  is_active boolean not null default true,
  rotated_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
insert into public.safe_elec_device_credentials(device_id,token_hash,is_active)
select sd.device_id,icd.token_hash,icd.status not in ('disabled','revoked')
from public.safe_elec_devices sd
join public.safe_elec_iot_core_mappings m on m.device_id=sd.device_id
join public.iot_core_devices icd on icd.id=m.iot_core_device_id
where icd.token_hash is not null
on conflict(device_id) do update set token_hash=excluded.token_hash,is_active=excluded.is_active,updated_at=now();

create table if not exists public.safe_elec_telemetry (
  id bigint generated always as identity primary key,
  project_id uuid not null references public.safe_elec_projects(id),
  device_id text not null references public.safe_elec_devices(device_id),
  source_iot_telemetry_id bigint unique,
  observed_at timestamptz,
  received_at timestamptz not null default now(),
  schema_version integer not null default 1,
  payload jsonb not null,
  quality jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists safe_elec_telemetry_device_received_idx on public.safe_elec_telemetry(device_id,received_at desc);
create index if not exists safe_elec_telemetry_project_received_idx on public.safe_elec_telemetry(project_id,received_at desc);

insert into public.safe_elec_telemetry(project_id,device_id,source_iot_telemetry_id,observed_at,received_at,schema_version,payload,quality)
select sp.id,sd.device_id,it.id,it.observed_at,it.received_at,it.schema_version,it.payload,it.quality
from public.iot_core_telemetry it
join public.iot_core_devices icd on icd.id=it.device_id
join public.iot_core_projects icp on icp.id=it.project_id and icp.project_key='safe-elec-v4-2'
join public.safe_elec_iot_core_mappings m on m.iot_core_device_id=icd.id
join public.safe_elec_devices sd on sd.device_id=m.device_id
join public.safe_elec_projects sp on sp.id=m.safe_elec_project_id
on conflict(source_iot_telemetry_id) do nothing;

update public.safe_elec_devices sd set last_seen=x.received_at,
is_online=(x.received_at >= now()-interval '90 seconds'),last_payload=x.payload,updated_at=now()
from (select distinct on(device_id) device_id,received_at,payload from public.safe_elec_telemetry
      order by device_id,received_at desc) x where x.device_id=sd.device_id;

alter table public.safe_elec_firmware_entitlements drop constraint if exists safe_elec_firmware_entitlements_project_id_fkey;
alter table public.safe_elec_firmware_entitlements add constraint safe_elec_firmware_entitlements_project_id_fkey foreign key(project_id) references public.safe_elec_projects(id);
alter table public.safe_elec_firmware_authorizations drop constraint if exists safe_elec_firmware_authorizations_project_id_fkey;
alter table public.safe_elec_firmware_authorizations add constraint safe_elec_firmware_authorizations_project_id_fkey foreign key(project_id) references public.safe_elec_projects(id);
alter table public.safe_elec_firmware_events drop constraint if exists safe_elec_firmware_events_project_id_fkey;
alter table public.safe_elec_firmware_events add constraint safe_elec_firmware_events_project_id_fkey foreign key(project_id) references public.safe_elec_projects(id);

update public.safe_elec_firmware_entitlements set project_id=(select id from public.safe_elec_projects where project_key='safe-elec-v4-2')
where project_id=(select id from public.iot_core_projects where project_key='safe-elec-v4-2');
update public.safe_elec_firmware_authorizations set project_id=(select id from public.safe_elec_projects where project_key='safe-elec-v4-2')
where project_id=(select id from public.iot_core_projects where project_key='safe-elec-v4-2');
update public.safe_elec_firmware_events set project_id=(select id from public.safe_elec_projects where project_key='safe-elec-v4-2')
where project_id=(select id from public.iot_core_projects where project_key='safe-elec-v4-2');

alter table public.safe_elec_projects enable row level security;
alter table public.safe_elec_iot_core_mappings enable row level security;
alter table public.safe_elec_device_credentials enable row level security;
alter table public.safe_elec_telemetry enable row level security;
drop policy if exists safe_elec_projects_owner_select on public.safe_elec_projects;
create policy safe_elec_projects_owner_select on public.safe_elec_projects for select to authenticated using(owner_user_id=(select auth.uid()));
drop policy if exists safe_elec_telemetry_owner_select on public.safe_elec_telemetry;
create policy safe_elec_telemetry_owner_select on public.safe_elec_telemetry for select to authenticated using(
 exists(select 1 from public.safe_elec_projects p where p.id=safe_elec_telemetry.project_id and p.owner_user_id=(select auth.uid()))
);
revoke all on public.safe_elec_iot_core_mappings from anon,authenticated;
revoke all on public.safe_elec_device_credentials from anon,authenticated;
grant select on public.safe_elec_projects,public.safe_elec_telemetry to authenticated;
grant all on public.safe_elec_projects,public.safe_elec_iot_core_mappings,public.safe_elec_device_credentials,public.safe_elec_telemetry to service_role;

create or replace function public.provision_safe_elec_device_credential(p_project_key text,p_device_key text,p_expected_role text,p_token_hash text)
returns table(device_key text,role text) language plpgsql security definer set search_path=public as $$
declare v_site_type text; v_role text;
begin
 if p_project_key<>'safe-elec-v4-2' or p_device_key not in ('SAFE-001','SAFE-001-BAK')
 or p_expected_role not in ('master','backup') or p_token_hash !~ '^[0-9a-f]{64}$' then
   raise exception 'INVALID_SAFE_ELEC_CREDENTIAL_REQUEST';
 end if;
 if not exists(select 1 from public.safe_elec_projects where project_key=p_project_key and status='active') then
   raise exception 'SAFE_ELEC_PROJECT_NOT_ACTIVE';
 end if;
 select site_type into v_site_type from public.safe_elec_devices where device_id=p_device_key;
 v_role:=case when v_site_type='main' then 'master' when v_site_type='backup' then 'backup' else null end;
 if v_role is null or v_role<>p_expected_role then raise exception 'SAFE_ELEC_DEVICE_ROLE_MISMATCH'; end if;
 insert into public.safe_elec_device_credentials(device_id,token_hash,is_active,rotated_at,updated_at)
 values(p_device_key,p_token_hash,true,now(),now())
 on conflict(device_id) do update set token_hash=excluded.token_hash,is_active=true,rotated_at=now(),updated_at=now();
 return query select p_device_key,v_role;
end; $$;
revoke all on function public.provision_safe_elec_device_credential(text,text,text,text) from public,anon,authenticated;
grant execute on function public.provision_safe_elec_device_credential(text,text,text,text) to service_role;
