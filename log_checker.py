"""
Verificador de Logs do Sistema Guardião Digital

Este script é o motor principal de monitoramento que escaneia diretórios de clientes,
analisa arquivos de log de backup e detecta falhas para acionar alertas automáticos.

Autor: Sistema Guardião Digital
Data: 2024
"""

import os
import re
import logging
import configparser
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Tuple, Optional

# Importar o módulo de alertas
try:
    from alerter import send_alert
except ImportError:
    logging.error("Módulo alerter.py não encontrado. Certifique-se de que está no mesmo diretório.")
    raise


class LogCheckerConfig:
    """
    Classe para gerenciar as configurações do verificador de logs.
    
    Carrega configurações específicas do log_checker do arquivo config.ini,
    incluindo diretórios de logs e padrões de arquivos.
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
        """
        try:
            self.config.read(self.config_file, encoding='utf-8')
        except Exception as e:
            logging.error(f"Erro ao carregar arquivo de configuração: {e}")
            raise
    
    def get_log_checker_config(self) -> dict:
        """
        Retorna as configurações específicas do verificador de logs.
        
        Returns:
            dict: Dicionário com configurações do log checker
        """
        return {
            'client_logs_dir': self.config.get('LOG_CHECKER', 'client_logs_dir', fallback='./client_logs/'),
            'log_file_pattern': self.config.get('LOG_CHECKER', 'log_file_pattern', fallback='CobianBackup_{date}.log'),
            'success_string': self.config.get('LOG_CHECKER', 'success_string', fallback='O backup foi concluído com sucesso'),
            'error_pattern': self.config.get('LOG_CHECKER', 'error_pattern', fallback=r'Erros:\s*(\d+)'),
            'check_previous_days': self.config.getint('LOG_CHECKER', 'check_previous_days', fallback=0),
            'enable_detailed_logging': self.config.getboolean('LOG_CHECKER', 'enable_detailed_logging', fallback=True)
        }


class BackupLogAnalyzer:
    """
    Classe responsável pela análise de arquivos de log de backup.
    
    Implementa a lógica de parsing dos logs para determinar se os backups
    foram executados com sucesso ou falharam.
    """
    
    def __init__(self, success_string: str, error_pattern: str):
        """
        Inicializa o analisador com os padrões de sucesso e erro.
        
        Args:
            success_string (str): String que indica sucesso no backup
            error_pattern (str): Padrão regex para detectar erros
        """
        self.success_string = success_string
        self.error_pattern = re.compile(error_pattern)
    
    def analyze_log_content(self, log_content: str) -> Tuple[bool, str]:
        """
        Analisa o conteúdo de um arquivo de log para determinar o status do backup.
        
        Args:
            log_content (str): Conteúdo completo do arquivo de log
            
        Returns:
            Tuple[bool, str]: (is_success, reason) - True se sucesso, False se falha
        """
        try:
            # Verificar se contém a string de sucesso
            has_success = self.success_string in log_content
            
            # Verificar se há erros reportados
            error_matches = self.error_pattern.findall(log_content)
            has_errors = False
            error_count = 0
            
            if error_matches:
                # Pegar o último match (mais recente)
                error_count = int(error_matches[-1])
                has_errors = error_count > 0
            
            # Determinar status final
            if has_success and not has_errors:
                return True, "Backup concluído com sucesso"
            elif has_success and has_errors:
                return False, f"Backup concluído mas com {error_count} erro(s) reportado(s)"
            elif not has_success and has_errors:
                return False, f"Backup falhou com {error_count} erro(s) reportado(s)"
            else:
                return False, "String de sucesso não encontrada no log"
                
        except Exception as e:
            logging.error(f"Erro ao analisar conteúdo do log: {e}")
            return False, f"Erro na análise do log: {str(e)}"
    
    def analyze_log_file(self, log_file_path: str) -> Tuple[bool, str]:
        """
        Analisa um arquivo de log específico.
        
        Args:
            log_file_path (str): Caminho para o arquivo de log
            
        Returns:
            Tuple[bool, str]: (is_success, reason) - True se sucesso, False se falha
        """
        try:
            with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as file:
                content = file.read()
                return self.analyze_log_content(content)
        except FileNotFoundError:
            return False, "Arquivo de log não encontrado"
        except PermissionError:
            return False, "Sem permissão para ler o arquivo de log"
        except Exception as e:
            logging.error(f"Erro ao ler arquivo de log {log_file_path}: {e}")
            return False, f"Erro ao ler arquivo: {str(e)}"


class ClientDirectoryScanner:
    """
    Classe responsável por escanear diretórios de clientes e localizar arquivos de log.
    
    Implementa a lógica de navegação pelos diretórios de clientes e busca
    por arquivos de log seguindo o padrão de nomenclatura especificado.
    """
    
    def __init__(self, base_directory: str, log_file_pattern: str):
        """
        Inicializa o scanner com o diretório base e padrão de arquivos.
        
        Args:
            base_directory (str): Diretório base onde estão as pastas dos clientes
            log_file_pattern (str): Padrão do nome do arquivo de log
        """
        self.base_directory = Path(base_directory)
        self.log_file_pattern = log_file_pattern
    
    def get_client_directories(self) -> List[str]:
        """
        Retorna uma lista de diretórios de clientes encontrados.
        
        Returns:
            List[str]: Lista com nomes dos diretórios de clientes
        """
        try:
            if not self.base_directory.exists():
                logging.warning(f"Diretório base não existe: {self.base_directory}")
                return []
            
            client_dirs = []
            for item in self.base_directory.iterdir():
                if item.is_dir():
                    client_dirs.append(item.name)
            
            logging.info(f"Encontrados {len(client_dirs)} diretórios de clientes")
            return sorted(client_dirs)
            
        except Exception as e:
            logging.error(f"Erro ao escanear diretórios de clientes: {e}")
            return []
    
    def get_log_file_path(self, client_name: str, target_date: datetime) -> str:
        """
        Constrói o caminho para o arquivo de log de um cliente em uma data específica.
        
        Args:
            client_name (str): Nome do cliente
            target_date (datetime): Data alvo para o arquivo de log
            
        Returns:
            str: Caminho completo para o arquivo de log
        """
        date_str = target_date.strftime("%Y-%m-%d")
        log_filename = self.log_file_pattern.format(date=date_str)
        return str(self.base_directory / client_name / log_filename)
    
    def find_latest_log_file(self, client_name: str, days_back: int = 3) -> Optional[str]:
        """
        Procura pelo arquivo de log mais recente de um cliente.
        
        Args:
            client_name (str): Nome do cliente
            days_back (int): Quantos dias para trás procurar
            
        Returns:
            Optional[str]: Caminho do arquivo encontrado ou None
        """
        client_dir = self.base_directory / client_name
        if not client_dir.exists():
            return None
        
        # Procurar por arquivos de log nos últimos dias
        for i in range(days_back + 1):
            check_date = datetime.now() - timedelta(days=i)
            log_path = self.get_log_file_path(client_name, check_date)
            
            if os.path.exists(log_path):
                logging.info(f"Arquivo de log encontrado para {client_name}: {log_path}")
                return log_path
        
        return None


class GuardiaoDigitalLogChecker:
    """
    Classe principal do sistema de verificação de logs.
    
    Coordena todas as operações de escaneamento, análise e alertas
    do sistema Guardião Digital.
    """
    
    def __init__(self, config_file: str = 'config.ini'):
        """
        Inicializa o verificador de logs com as configurações especificadas.
        
        Args:
            config_file (str): Caminho para o arquivo de configuração
        """
        self.config_file = config_file
        self.config_manager = LogCheckerConfig(config_file)
        self.config = self.config_manager.get_log_checker_config()
        
        # Inicializar componentes
        self.scanner = ClientDirectoryScanner(
            self.config['client_logs_dir'],
            self.config['log_file_pattern']
        )
        
        self.analyzer = BackupLogAnalyzer(
            self.config['success_string'],
            self.config['error_pattern']
        )
        
        # Configurar logging
        if self.config['enable_detailed_logging']:
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
    
    def check_client_backup(self, client_name: str, target_date: datetime = None) -> Dict[str, any]:
        """
        Verifica o status do backup de um cliente específico.
        
        Args:
            client_name (str): Nome do cliente
            target_date (datetime): Data alvo (padrão: hoje)
            
        Returns:
            Dict[str, any]: Resultado da verificação com status e detalhes
        """
        if target_date is None:
            target_date = datetime.now()
        
        result = {
            'client_name': client_name,
            'date': target_date.strftime('%Y-%m-%d'),
            'success': False,
            'reason': '',
            'log_file_found': False,
            'log_file_path': ''
        }
        
        try:
            # Procurar arquivo de log
            log_file_path = self.scanner.get_log_file_path(client_name, target_date)
            
            if not os.path.exists(log_file_path):
                # Tentar encontrar log mais recente se configurado
                if self.config['check_previous_days'] > 0:
                    log_file_path = self.scanner.find_latest_log_file(
                        client_name, 
                        self.config['check_previous_days']
                    )
                
                if not log_file_path or not os.path.exists(log_file_path):
                    result['reason'] = f"Arquivo de log não encontrado para a data {target_date.strftime('%Y-%m-%d')}"
                    return result
            
            result['log_file_found'] = True
            result['log_file_path'] = log_file_path
            
            # Analisar conteúdo do log
            success, reason = self.analyzer.analyze_log_file(log_file_path)
            result['success'] = success
            result['reason'] = reason
            
            logging.info(f"Cliente {client_name}: {'SUCESSO' if success else 'FALHA'} - {reason}")
            
        except Exception as e:
            result['reason'] = f"Erro durante verificação: {str(e)}"
            logging.error(f"Erro ao verificar cliente {client_name}: {e}")
        
        return result
    
    def check_all_clients(self, target_date: datetime = None) -> List[Dict[str, any]]:
        """
        Verifica o status de backup de todos os clientes.
        
        Args:
            target_date (datetime): Data alvo (padrão: hoje)
            
        Returns:
            List[Dict[str, any]]: Lista com resultados de todos os clientes
        """
        if target_date is None:
            target_date = datetime.now()
        
        logging.info(f"Iniciando verificação de todos os clientes para {target_date.strftime('%Y-%m-%d')}")
        
        clients = self.scanner.get_client_directories()
        results = []
        
        for client_name in clients:
            result = self.check_client_backup(client_name, target_date)
            results.append(result)
        
        return results
    
    def process_failures_and_alert(self, results: List[Dict[str, any]]) -> Dict[str, int]:
        """
        Processa os resultados e envia alertas para falhas detectadas.
        
        Args:
            results (List[Dict[str, any]]): Lista de resultados das verificações
            
        Returns:
            Dict[str, int]: Estatísticas dos alertas enviados
        """
        stats = {
            'total_clients': len(results),
            'successful_backups': 0,
            'failed_backups': 0,
            'alerts_sent': 0
        }
        
        for result in results:
            if result['success']:
                stats['successful_backups'] += 1
            else:
                stats['failed_backups'] += 1
                
                # Enviar alerta
                try:
                    alert_result = send_alert(
                        client_name=result['client_name'],
                        status="FALHA",
                        reason=result['reason'],
                        config_file=self.config_file
                    )
                    
                    if alert_result['email_sent'] or alert_result['telegram_sent']:
                        stats['alerts_sent'] += 1
                        logging.info(f"Alerta enviado para cliente {result['client_name']}")
                    else:
                        logging.warning(f"Falha ao enviar alerta para cliente {result['client_name']}")
                        
                except Exception as e:
                    logging.error(f"Erro ao enviar alerta para {result['client_name']}: {e}")
        
        return stats
    
    def run_daily_check(self) -> None:
        """
        Executa a verificação diária completa de todos os clientes.
        
        Esta é a função principal que deve ser chamada pelo agendador de tarefas
        ou executada manualmente para verificar todos os backups do dia.
        """
        logging.info("=== INICIANDO VERIFICAÇÃO DIÁRIA GUARDIÃO DIGITAL ===")
        
        try:
            # Verificar todos os clientes
            results = self.check_all_clients()
            
            # Processar falhas e enviar alertas
            stats = self.process_failures_and_alert(results)
            
            # Log de estatísticas finais
            logging.info("=== RESUMO DA VERIFICAÇÃO ===")
            logging.info(f"Total de clientes: {stats['total_clients']}")
            logging.info(f"Backups bem-sucedidos: {stats['successful_backups']}")
            logging.info(f"Backups com falha: {stats['failed_backups']}")
            logging.info(f"Alertas enviados: {stats['alerts_sent']}")
            
            if stats['failed_backups'] == 0:
                logging.info("🎉 Todos os backups foram executados com sucesso!")
            else:
                logging.warning(f"⚠️ {stats['failed_backups']} backup(s) falharam e alertas foram enviados")
            
        except Exception as e:
            logging.error(f"Erro durante verificação diária: {e}")
            # Tentar enviar alerta sobre erro do sistema
            try:
                send_alert(
                    client_name="SISTEMA",
                    status="ERRO CRÍTICO",
                    reason=f"Falha na execução do verificador de logs: {str(e)}",
                    config_file=self.config_file
                )
            except:
                pass  # Se não conseguir enviar alerta, pelo menos loggar o erro


def main():
    """
    Função principal para execução do script.
    
    Pode ser executada diretamente ou importada por outros módulos.
    """
    try:
        checker = GuardiaoDigitalLogChecker()
        checker.run_daily_check()
    except Exception as e:
        logging.error(f"Erro crítico na execução: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())