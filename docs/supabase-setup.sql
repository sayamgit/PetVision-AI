-- Run once in the SQL Editor of the intended PetVision Supabase project.
-- Django migrations use a private schema, never the Data API's public schema.
CREATE SCHEMA IF NOT EXISTS petvision;
REVOKE ALL ON SCHEMA petvision FROM PUBLIC, anon, authenticated;
-- Leave the Data API disabled for this application.
-- Create the PRIVATE petvision-photos bucket using Storage in the dashboard.
