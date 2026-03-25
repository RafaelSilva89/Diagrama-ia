#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()

'''
Existem algumas formas de recuperar o acesso ao Django Admin. Veja as opções:       
  Opção 1: Criar um novo superusuário                                              
  
  No terminal, dentro do diretório do projeto (onde está o manage.py):                                                                                                
  python manage.py createsuperuser

  Isso te pedirá um novo username, email e senha.

  rafael
  123456
  
  '''