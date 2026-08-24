-- DOOF v0.3 model registry (metadata only — blobs live in object storage/CDN)

CREATE TABLE IF NOT EXISTS public.model_registry (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  model_id text NOT NULL,
  version text NOT NULL,
  label text,
  format text DEFAULT 'doof-pt',
  size_bytes bigint DEFAULT 0,
  sha256 text,
  download_url text,
  channel text DEFAULT 'stable',
  status text DEFAULT 'approved',
  cpu_supported boolean DEFAULT true,
  gpu_supported boolean DEFAULT true,
  min_ram_gb real DEFAULT 4,
  recommended_ram_gb real DEFAULT 8,
  min_vram_gb real DEFAULT 0,
  recommended_vram_gb real DEFAULT 0,
  notes text,
  created_at timestamptz DEFAULT now(),
  UNIQUE (model_id, version)
);

CREATE INDEX IF NOT EXISTS idx_model_registry_status ON public.model_registry (status);

ALTER TABLE public.model_registry ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS model_registry_read ON public.model_registry;
CREATE POLICY model_registry_read ON public.model_registry
  FOR SELECT TO authenticated
  USING (status IN ('approved', 'candidate'));

-- Hosted brain service rows (optional inventory of DOOF-owned inference endpoints)
CREATE TABLE IF NOT EXISTS public.hosted_services (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  kind text DEFAULT 'brain',
  base_url text NOT NULL,
  model_id text,
  model_version text,
  status text DEFAULT 'online',
  capacity int DEFAULT 1,
  last_health_at timestamptz,
  created_at timestamptz DEFAULT now()
);

ALTER TABLE public.hosted_services ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS hosted_services_read ON public.hosted_services;
CREATE POLICY hosted_services_read ON public.hosted_services
  FOR SELECT TO authenticated
  USING (true);
