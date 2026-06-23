-- 仅允许 @transsion.com 邮箱注册（服务端校验，防止绕过前端）
CREATE OR REPLACE FUNCTION public.enforce_transsion_email_domain()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = auth, public
AS $$
BEGIN
  IF NEW.email IS NULL OR lower(split_part(NEW.email, '@', 2)) <> 'transsion.com' THEN
    RAISE EXCEPTION '仅允许使用 @transsion.com 邮箱注册';
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS enforce_transsion_email_domain ON auth.users;
CREATE TRIGGER enforce_transsion_email_domain
  BEFORE INSERT ON auth.users
  FOR EACH ROW
  EXECUTE FUNCTION public.enforce_transsion_email_domain();
