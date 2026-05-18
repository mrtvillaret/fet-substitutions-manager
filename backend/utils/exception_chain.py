"""
Exception Handler Chain per manejo robusto d'errors
Consolidació de patrons d'excepció i logging across modules
"""
import logging
import traceback
from typing import Type, List, Callable, Optional, Any, Dict
from functools import wraps
from enum import Enum
from dataclasses import dataclass
import i18n_setup

_ = i18n_setup._

class ErrorSeverity(Enum):
    """Nivells de severitat d'errors"""
    LOW = "low"
    MEDIUM = "medium" 
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class ErrorContext:
    """Context d'error amb metadata"""
    operation: str
    user_message: str
    technical_details: str
    severity: ErrorSeverity
    recoverable: bool = True
    retry_count: int = 0

class ExceptionHandler:
    """Handler individual per un tipus d'excepció"""
    
    def __init__(
        self, 
        exception_type: Type[Exception],
        context: ErrorContext,
        handler_func: Optional[Callable] = None
    ):
        self.exception_type = exception_type
        self.context = context
        self.handler_func = handler_func or self._default_handler
        
    def _default_handler(self, exception: Exception, operation_context: Dict = None):
        """Handler per defecte amb logging"""
        logging.error(
            f"[{self.context.severity.value.upper()}] {self.context.operation}: "
            f"{self.context.technical_details} - {str(exception)}"
        )
        return self.context.user_message
        
    def handle(self, exception: Exception, operation_context: Dict = None):
        """Maneja l'excepció amb el handler específic"""
        return self.handler_func(exception, operation_context)

class ExceptionChain:
    """Cadena d'handlers d'excepcions amb logging centralized"""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.handlers: List[ExceptionHandler] = []
        self.default_context = ErrorContext(
            operation=_("operació desconeguda"),
            user_message=_("Error inesperat"),
            technical_details=_("Excepció no gestionada"),
            severity=ErrorSeverity.MEDIUM
        )
        
    def add_handler(self, handler: ExceptionHandler):
        """Afegeix handler a la cadena"""
        self.handlers.append(handler)
        return self
        
    def add_simple_handler(
        self,
        exception_type: Type[Exception],
        operation: str,
        user_message: str,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        recoverable: bool = True
    ):
        """Afegeix handler simple amb paràmetres"""
        context = ErrorContext(
            operation=operation,
            user_message=user_message,
            technical_details=_("Error en {}").format(operation),
            severity=severity,
            recoverable=recoverable
        )
        handler = ExceptionHandler(exception_type, context)
        return self.add_handler(handler)
        
    def handle_exception(self, exception: Exception, operation_context: Dict = None) -> str:
        """Gestiona excepció amb la cadena d'handlers"""
        exception_type = type(exception)
        
        # Busca handler específic
        for handler in self.handlers:
            if issubclass(exception_type, handler.exception_type):
                return handler.handle(exception, operation_context)
                
        # Handler per defecte
        self.logger.error(
            f"[{self.default_context.severity.value.upper()}] "
            f"{self.default_context.operation}: {str(exception)}\n"
            f"Traceback: {traceback.format_exc()}"
        )
        return self.default_context.user_message
        
    def create_decorator(self, operation: str, user_message: str = None):
        """Crea decorator per funcions amb aquesta cadena"""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    error_msg = self.handle_exception(e, {
                        'function': func.__name__,
                        'operation': operation,
                        'args': len(args),
                        'kwargs': list(kwargs.keys())
                    })
                    # Retorna None o error message segons context
                    return None if user_message is None else error_msg
            return wrapper
        return decorator

# Instàncies predefinides per diferents modules
def create_gui_exception_chain() -> ExceptionChain:
    """Cadena d'excepcions per mòduls GUI"""
    chain = ExceptionChain()
    
    # File I/O errors
    chain.add_simple_handler(
        FileNotFoundError,
        _("accés a fitxer"),
        _("Fitxer no trobat. Comprova que el fitxer existeix."),
        ErrorSeverity.MEDIUM
    )
    
    chain.add_simple_handler(
        PermissionError,
        _("accés a fitxer"),
        _("Permisos insuficients per accedir al fitxer."),
        ErrorSeverity.HIGH
    )
    
    # JSON errors
    chain.add_simple_handler(
        ValueError,
        _("processament de dades"),
        _("Error en format de dades. Comprova l'entrada."),
        ErrorSeverity.MEDIUM
    )
    
    # Connection errors
    chain.add_simple_handler(
        ConnectionError,
        _("connexió externa"),
        _("Error de connexió. Comprova la connectivitat."),
        ErrorSeverity.HIGH
    )
    
    return chain

def create_data_exception_chain() -> ExceptionChain:
    """Cadena d'excepcions per mòduls de dades"""
    chain = ExceptionChain()
    
    # JSON parsing
    import json
    chain.add_simple_handler(
        json.JSONDecodeError,
        _("descodificació JSON"),
        _("Format de fitxer corrupte. Regenera el fitxer."),
        ErrorSeverity.HIGH
    )
    
    # Key errors
    chain.add_simple_handler(
        KeyError,
        _("accés a dades"),
        _("Dada no trobada. Comprova la configuració."),
        ErrorSeverity.MEDIUM
    )
    
    # Type errors
    chain.add_simple_handler(
        TypeError,
        _("tipus de dades"),
        _("Error en tipus de dada. Comprova l'entrada."),
        ErrorSeverity.MEDIUM
    )
    
    return chain

def create_core_exception_chain() -> ExceptionChain:
    """Cadena d'excepcions per mòduls core"""
    chain = ExceptionChain()
    
    # Index errors
    chain.add_simple_handler(
        IndexError,
        _("accés a llista"),
        _("Índex fora de rang. Comprova les dades."),
        ErrorSeverity.MEDIUM
    )
    
    # Attribute errors
    chain.add_simple_handler(
        AttributeError,
        _("accés a propietat"),
        _("Propietat no trobada. Comprova l'objecte."),
        ErrorSeverity.MEDIUM
    )
    
    # Division by zero
    chain.add_simple_handler(
        ZeroDivisionError,
        _("càlcul matemàtic"),
        _("Divisió per zero. Comprova els valors."),
        ErrorSeverity.HIGH
    )
    
    return chain

# Decoradors globals predefinits
gui_error_handler = create_gui_exception_chain()
data_error_handler = create_data_exception_chain()
core_error_handler = create_core_exception_chain()

# Decoradors d'ús comú
safe_gui_operation = gui_error_handler.create_decorator
safe_data_operation = data_error_handler.create_decorator
safe_core_operation = core_error_handler.create_decorator
