"""
Módulo de Alertas para o Sistema Guardião Digital

Este módulo fornece funcionalidades para envio de notificações por email e Telegram
quando falhas de backup são detectadas no sistema de monitoramento.

Autor: Sistema Guardião Digital
Data: 2024
"""

import smtplib
import configparser
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Optional

try:
    from telegram import Bot
    from telegram.error import TelegramError
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    logging.warning("Biblioteca python-telegram-bot não encontrada. Notificações Telegram desabilitadas.")


class AlerterConfig:
    """
    Classe para gerenciar as configurações do sistema de alertas.
    
    Carrega configurações do arquivo config.ini incluindo credenciais de email,
    configurações do Telegram e outras opções do sistema.
    """
    
    def __init__(self, config_file: str = 'config.ini'):
        """
        Inicializa a configuração carregando o arquivo especificado.
        
        Args:
            config_file (str): Caminho para o arquivo de configuração
        """
        self.config = configparser.ConfigParser()
        self.config_file = config_file
        self.load_config()
    
    def load_config(self) -> None:
        """
        Carrega as configurações do arquivo config.ini.
        
        Raises:
            FileNotFoundError: Se o arquivo de configuração não for encontrado
            configparser.Error: Se houver erro na leitura do arquivo
        """
        try:
            self.config.read(self.config_file, encoding='utf-8')
        except Exception as e:
            logging.error(f"Erro ao carregar arquivo de configuração: {e}")
            raise
    
    def get_email_config(self) -> dict:
        """
        Retorna as configurações de email.
        
        Returns:
            dict: Dicionário com configurações de email
        """
        return {
            'smtp_server': self.config.get('EMAIL', 'smtp_server', fallback='smtp.gmail.com'),
            'smtp_port': self.config.getint('EMAIL', 'smtp_port', fallback=587),
            'username': self.config.get('EMAIL', 'username'),
            'password': self.config.get('EMAIL', 'password'),
            'from_email': self.config.get('EMAIL', 'from_email'),
            'to_email': self.config.get('EMAIL', 'to_email')
        }
    
    def get_telegram_config(self) -> dict:
        """
        Retorna as configurações do Telegram.
        
        Returns:
            dict: Dicionário com configurações do Telegram
        """
        return {
            'bot_token': self.config.get('TELEGRAM', 'bot_token', fallback=''),
            'chat_id': self.config.get('TELEGRAM', 'chat_id', fallback='')
        }
    
    def get_general_config(self) -> dict:
        """
        Retorna as configurações gerais do sistema.
        
        Returns:
            dict: Dicionário com configurações gerais
        """
        return {
            'enable_email': self.config.getboolean('GENERAL', 'enable_email', fallback=True),
            'enable_telegram': self.config.getboolean('GENERAL', 'enable_telegram', fallback=True),
            'log_level': self.config.get('GENERAL', 'log_level', fallback='INFO')
        }


class EmailNotifier:
    """
    Classe responsável pelo envio de notificações por email.
    
    Utiliza SMTP para enviar emails formatados em HTML com informações
    sobre falhas de backup detectadas.
    """
    
    def __init__(self, config: dict):
        """
        Inicializa o notificador de email com as configurações fornecidas.
        
        Args:
            config (dict): Dicionário com configurações de email
        """
        self.smtp_server = config['smtp_server']
        self.smtp_port = config['smtp_port']
        self.username = config['username']
        self.password = config['password']
        self.from_email = config['from_email']
        self.to_email = config['to_email']
    
    def send_email(self, client_name: str, status: str, reason: str) -> bool:
        """
        Envia um email de alerta sobre falha de backup.
        
        Args:
            client_name (str): Nome do cliente afetado
            status (str): Status do backup (FALHA, SUCESSO, etc.)
            reason (str): Motivo da falha ou detalhes adicionais
            
        Returns:
            bool: True se o email foi enviado com sucesso, False caso contrário
        """
        try:
            # Criar mensagem
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"🚨 Alerta Guardião Digital - {client_name}"
            msg['From'] = self.from_email
            msg['To'] = self.to_email
            
            # Criar conteúdo HTML
            html_content = self._create_html_content(client_name, status, reason)
            html_part = MIMEText(html_content, 'html', 'utf-8')
            msg.attach(html_part)
            
            # Enviar email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
            
            logging.info(f"Email enviado com sucesso para {self.to_email}")
            return True
            
        except Exception as e:
            logging.error(f"Erro ao enviar email: {e}")
            return False
    
    def _create_html_content(self, client_name: str, status: str, reason: str) -> str:
        """
        Cria o conteúdo HTML para o email de alerta.
        
        Args:
            client_name (str): Nome do cliente
            status (str): Status do backup
            reason (str): Motivo da falha
            
        Returns:
            str: Conteúdo HTML formatado
        """
        timestamp = datetime.now().strftime("%d/%m/%Y às %H:%M:%S")
        
        html_template = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background-color: #dc3545; color: white; padding: 15px; border-radius: 5px; }}
                .content {{ background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin-top: 10px; }}
                .info {{ margin: 10px 0; }}
                .footer {{ margin-top: 20px; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h2>🚨 Alerta de Falha de Backup - Guardião Digital</h2>
            </div>
            <div class="content">
                <div class="info"><strong>Cliente:</strong> {client_name}</div>
                <div class="info"><strong>Status:</strong> {status}</div>
                <div class="info"><strong>Motivo:</strong> {reason}</div>
                <div class="info"><strong>Data/Hora:</strong> {timestamp}</div>
            </div>
            <div class="footer">
                <p>Este é um alerta automático do sistema Guardião Digital.</p>
                <p>Por favor, verifique o backup do cliente o mais breve possível.</p>
            </div>
        </body>
        </html>
        """
        return html_template


class TelegramNotifier:
    """
    Classe responsável pelo envio de notificações via Telegram.
    
    Utiliza a API do Telegram Bot para enviar mensagens formatadas
    sobre falhas de backup detectadas.
    """
    
    def __init__(self, config: dict):
        """
        Inicializa o notificador do Telegram com as configurações fornecidas.
        
        Args:
            config (dict): Dicionário com configurações do Telegram
        """
        self.bot_token = config['bot_token']
        self.chat_id = config['chat_id']
        self.bot = None
        
        if TELEGRAM_AVAILABLE and self.bot_token:
            try:
                self.bot = Bot(token=self.bot_token)
            except Exception as e:
                logging.error(f"Erro ao inicializar bot do Telegram: {e}")
    
    def send_telegram_message(self, client_name: str, status: str, reason: str) -> bool:
        """
        Envia uma mensagem via Telegram sobre falha de backup.
        
        Args:
            client_name (str): Nome do cliente afetado
            status (str): Status do backup
            reason (str): Motivo da falha ou detalhes adicionais
            
        Returns:
            bool: True se a mensagem foi enviada com sucesso, False caso contrário
        """
        if not TELEGRAM_AVAILABLE:
            logging.warning("Biblioteca python-telegram-bot não disponível")
            return False
        
        if not self.bot or not self.chat_id:
            logging.warning("Bot do Telegram não configurado corretamente")
            return False
        
        try:
            timestamp = datetime.now().strftime("%d/%m/%Y às %H:%M:%S")
            
            message = f"""
🚨 *ALERTA GUARDIÃO DIGITAL*

👤 *Cliente:* {client_name}
📊 *Status:* {status}
❌ *Motivo:* {reason}
🕐 *Data/Hora:* {timestamp}

⚠️ Verifique o backup do cliente imediatamente!
            """.strip()
            
            self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='Markdown'
            )
            
            logging.info(f"Mensagem Telegram enviada com sucesso para chat {self.chat_id}")
            return True
            
        except TelegramError as e:
            logging.error(f"Erro do Telegram: {e}")
            return False
        except Exception as e:
            logging.error(f"Erro ao enviar mensagem Telegram: {e}")
            return False


def send_alert(client_name: str, status: str, reason: str, config_file: str = 'config.ini') -> dict:
    """
    Função principal para envio de alertas via email e/ou Telegram.
    
    Esta é a função principal que deve ser chamada pelo log_checker.py
    para enviar notificações quando falhas de backup são detectadas.
    
    Args:
        client_name (str): Nome do cliente afetado
        status (str): Status do backup (ex: "FALHA", "ERRO")
        reason (str): Motivo da falha ou detalhes adicionais
        config_file (str): Caminho para o arquivo de configuração
        
    Returns:
        dict: Dicionário com resultados do envio (email_sent, telegram_sent)
    """
    results = {'email_sent': False, 'telegram_sent': False}
    
    try:
        # Carregar configurações
        config_manager = AlerterConfig(config_file)
        general_config = config_manager.get_general_config()
        
        # Configurar logging
        log_level = getattr(logging, general_config['log_level'].upper(), logging.INFO)
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        logging.info(f"Enviando alerta para cliente: {client_name}")
        
        # Enviar email se habilitado
        if general_config['enable_email']:
            try:
                email_config = config_manager.get_email_config()
                email_notifier = EmailNotifier(email_config)
                results['email_sent'] = email_notifier.send_email(client_name, status, reason)
            except Exception as e:
                logging.error(f"Erro ao processar notificação por email: {e}")
        
        # Enviar Telegram se habilitado
        if general_config['enable_telegram']:
            try:
                telegram_config = config_manager.get_telegram_config()
                telegram_notifier = TelegramNotifier(telegram_config)
                results['telegram_sent'] = telegram_notifier.send_telegram_message(client_name, status, reason)
            except Exception as e:
                logging.error(f"Erro ao processar notificação Telegram: {e}")
        
        return results
        
    except Exception as e:
        logging.error(f"Erro geral no sistema de alertas: {e}")
        return results


if __name__ == "__main__":
    # Teste do módulo
    print("Testando módulo de alertas...")
    result = send_alert("Cliente Teste", "FALHA", "Arquivo de log não encontrado")
    print(f"Resultados do teste: {result}")