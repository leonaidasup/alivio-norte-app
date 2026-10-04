import logging
import os
import yaml
import shutil
from pathlib import Path

log = logging.getLogger("alivio.rules")

BASIC_RULES = ["riesgo", "reglas_monto", "deudas_elegibles", "deudas_no_elegibles",
               "ignorar", "categorias_escalar_humano", "precalificacion", "compliance"]


class RulesError(Exception):
    """Error de las reglas de negocio (YAML vacío, incompleto o inválido)."""


def load_rules(path) -> dict:
    """Carga las reglas y verifica que sean válidas y utilizables."""
    with open(path, encoding="utf-8") as f:
        rules = yaml.safe_load(f)
    if not isinstance(rules, dict):
        raise RulesError(f"{path} vacío o con formato inválido")

    # Verificar que existan las secciones básicas
    missing = [k for k in BASIC_RULES if k not in rules]
    if missing:
        raise RulesError(f"Faltan secciones en {path}: {missing}")

    # Verificar que cada categoría de escalamiento tenga un peso numérico
    for name, cat in rules["categorias_escalar_humano"].items():
        if not isinstance(cat.get("peso"), (int, float)):
            raise RulesError(f"Categoría '{name}' necesita un 'peso' numérico")
    return rules


class RulesStore:
    """Carga las reglas con recarga en caliente y respaldo de la ultima version valida.
    - Si se edita config/rules.yaml con el sistema corriendo, el siguiente mensaje usa la nueva.
    - Si queda invalido con el sistema corriendo se usan las anteriores reglas validas.
    - Si queda inválido y el sistema se reinicia se usa la copia en disco de la ultima version valida (.../runtime/rules.last_good.yaml).
    """

    def __init__(self, path, backup_path=None):
        self.path = Path(path)
        self.backup_path = Path(backup_path) if backup_path else self.path.parent.parent / "runtime" / "rules.last_good.yaml"
        self._mtime = None
        self._rules = None

    def get(self) -> dict:
        mtime = self.path.stat().st_mtime
        if mtime != self._mtime: # verificar el archivo rules.yaml no se actualizara, en caso de ser así se carga nuevamente
            try:
                self._rules = load_rules(self.path)
                self.save_backup_rules()
                log.info("Reglas cargadas (versión %s)", self._rules.get("version"))
            except Exception as e: # si el rules.yaml tiene algun error usamos las reglas cargadas previamente o respaldo
                if self._rules is None:
                    self._rules = self.load_backup_rules(e)
                else:
                    log.warning(f'{self.path} inválido, se conservan las reglas anteriores: %s', e)
            self._mtime = mtime
        return self._rules

    def save_backup_rules(self):
        """Copia primero a un temporal y luego se reemplaza"""
        self.backup_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.backup_path.with_suffix(".tmp")
        shutil.copy2(self.path, tmp)
        os.replace(tmp, self.backup_path)

    def load_backup_rules(self, error: Exception) -> dict:
        if self.backup_path.exists():
            try:
                rules = load_rules(self.backup_path)
                log.warning(f"{self.path} inválido (%s). Se usa el respaldo de la ultima versión válida: %s", error, self.backup_path)
                return rules
            except Exception as e2:
                log.error("El respaldo tampoco es válido: %s", e2)
        raise RulesError(f"{self.path} inválido y no hay respaldo utilizable: {error}") from error