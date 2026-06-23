-- RAGmind storage: private 'documents' bucket for uploaded PDFs.
-- Each user can only touch files under a folder named after their uid:
--   documents/<user_id>/<filename>.pdf

insert into storage.buckets (id, name, public)
values ('documents', 'documents', false)
on conflict (id) do nothing;

-- Owner-scoped policies. (storage.foldername(name))[1] = first path segment = uid.

create policy "documents_storage_select_own" on storage.objects
  for select using (
    bucket_id = 'documents'
    and (storage.foldername(name))[1] = auth.uid()::text
  );

create policy "documents_storage_insert_own" on storage.objects
  for insert with check (
    bucket_id = 'documents'
    and (storage.foldername(name))[1] = auth.uid()::text
  );

create policy "documents_storage_delete_own" on storage.objects
  for delete using (
    bucket_id = 'documents'
    and (storage.foldername(name))[1] = auth.uid()::text
  );
