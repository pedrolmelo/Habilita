-- infra/storage/00-init.sql
-- Script de inicialização do PostgreSQL para o Supabase Storage API local.
-- Cria os papéis e permissões necessárias antes da execução das migrações do storage-api.

-- 1. Criação dos papéis padrão do ecossistema Supabase
CREATE ROLE anon NOLOGIN NOINHERIT;
CREATE ROLE authenticated NOLOGIN NOINHERIT;
CREATE ROLE service_role NOLOGIN NOINHERIT BYPASSRLS;
CREATE ROLE supabase_storage_admin LOGIN PASSWORD 'postgres' SUPERUSER;
CREATE ROLE authenticator LOGIN NOINHERIT;

-- 2. Concessão de papéis ao authenticator
GRANT anon TO authenticator;
GRANT authenticated TO authenticator;
GRANT service_role TO authenticator;
GRANT ALL PRIVILEGES ON DATABASE postgres TO supabase_storage_admin;

-- 3. Configuração de search_path padrão para os papéis do Storage
ALTER ROLE anon SET search_path = storage, public;
ALTER ROLE authenticated SET search_path = storage, public;
ALTER ROLE service_role SET search_path = storage, public;
ALTER ROLE supabase_storage_admin SET search_path = storage, public;

-- 4. Criação do schema storage e privilégios padrão
CREATE SCHEMA IF NOT EXISTS storage AUTHORIZATION supabase_storage_admin;
GRANT ALL ON SCHEMA storage TO postgres, anon, authenticated, service_role, supabase_storage_admin;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_storage_admin IN SCHEMA storage GRANT ALL ON TABLES TO postgres, anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_storage_admin IN SCHEMA storage GRANT ALL ON ROUTINES TO postgres, anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_storage_admin IN SCHEMA storage GRANT ALL ON SEQUENCES TO postgres, anon, authenticated, service_role;
