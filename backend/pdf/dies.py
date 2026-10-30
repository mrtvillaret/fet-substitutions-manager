"""Abreviatures dels dies de la setmana a les capçaleres de taula dels informes
(les normatives: dl., dt., dc., dj., dv.; amb majúscula, perquè encapçalen
una columna)."""

from i18n_setup import translate as _


def dies_capcalera() -> list:
    """Dilluns a divendres, abreujats i traduïts."""
    return [_("Dl."), _("Dt."), _("Dc."), _("Dj."), _("Dv.")]
