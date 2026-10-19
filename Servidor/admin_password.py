"""Definir / alterar senha da conta Admin pelo console do servidor."""
import getpass, sys, secrets, hashlib, json
from pathlib import Path
DATA=Path(__file__).resolve().parent.parent/'Dados'
CONFIG=DATA/'privacidade.json'
def main():
 DATA.mkdir(exist_ok=True)
 if CONFIG.exists():
  print('ALTERAR SENHA DO ADMIN (nenhuma senha aparece na tela)')
  from server import check_password
  try:cfg=json.loads(CONFIG.read_text(encoding='utf-8'))
  except Exception:raise SystemExit('Arquivo de senha invalido: verifique o backup antes de continuar.')
  if not check_password(getpass.getpass('Senha atual: '),cfg):raise SystemExit('Senha atual incorreta.')
 else:
  print('CRIAR SENHA DO ADMIN (nunca gravada em texto puro)')
 pw=getpass.getpass('Nova senha (minimo 10 caracteres): ')
 if len(pw)<10 or len(pw)>200:raise SystemExit('A senha precisa ter entre 10 e 200 caracteres.')
 if pw!=getpass.getpass('Repetir nova senha: '):raise SystemExit('As senhas nao coincidem.')
 salt=secrets.token_bytes(16); rounds=350000
 cfg={'salt':salt.hex(),'rounds':rounds,'hash':hashlib.pbkdf2_hmac('sha256',pw.encode(),salt,rounds).hex()}
 temp=CONFIG.with_suffix('.tmp')
 temp.write_text(json.dumps(cfg),encoding='utf-8');temp.replace(CONFIG)
 print('Senha atualizada. Sessoes antigas expiram automaticamente.')
if __name__=='__main__':
 try:main()
 except KeyboardInterrupt:print('Cancelado.')
