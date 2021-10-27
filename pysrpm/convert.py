""" Utility functions to convert complex python dependency expressions to a format that is usable in RPM spec files """
from packaging.markers import Marker

_rpm_operator_correspondance = {
    '==': '=',
    '===': '=',
    '<': '<',
    '<=': '<=',
    '>=': '>=',
    '>': '>',
}


def _single_marker_to_rpm_condition(marker, templates):
    """ Helper for :func:`~simplify_marker_to_rpm_condition` that expresses a single-cluse marker as a string

    Args:
        marker (`tuple`): A leaf of :class:`~packaging.markers.Marker`’s `_marker` attribute
        templates (`dict`): templates for python version and architecture

    Returns:
        `str`: The RPM-compatible string representation of the marker
    """
    operator, version = marker[1].value, marker[2].value
    if marker[0].value == 'platform_machine':  # arch / uname -m
        arch_template = templates['python_arch']
        if operator == '==':
            return 'if ' + arch_template.format(arch=version)
        elif operator == '!=':
            return 'without ' + arch_template.format(arch=version)
        elif operator == 'in':
            return f'if ({" or ".join(arch_template.format(arch=arch) for arch in version.split())})'
        else:
            raise ValueError(f'Unsupported operator {operator} for platform_machine')

    elif marker[0].value in {'python_full_version', 'python_version', 'implementation_version'}:
        package = templates['python_abi']
    elif marker[0].value == 'platform_release':
        package = 'kernel'
    else:
        raise ValueError(f'Unsupported marker {marker[0].value}')

    rpm_op = _rpm_operator_correspondance.get(operator)
    if rpm_op is not None:
        return f'{package} {rpm_op} {version}'
    elif operator == '~=':
        return f'({package} >= {version} and {package} < {version}^next)'
    elif operator == '!=':
        return f'({package} < {version} or {package} > {version})'
    elif operator == 'in':
        return f'({" or ".join(f"{package} = {each_version}" for each_version in version.split())})'
    else:
        raise ValueError(f'Unsupported operator {operator} for dependency marker {marker}')


def simplify_marker_to_rpm_condition(marker, environments, templates):
    """ Express a dependency marker in terms useful for RPM packaging, evaluate clauses in the marker if possible

    This should remove markers that are always false in the given environments, identify markers that are always true,
    and return a RPM-spec compliant string condition for any remaining clauses

    Args:
        marker (:class:`~packaging.markers.Marker`): The marker to evaluate
        environments (`dict`): the possible environments, with keys are PEP508 environment markers, values are either
                               a single value as a string, or a list of strings for possible values
       templates (`dict`): templates to express python version (`python_abi`) and architecture (`python_arch`)

    Returns:
        `str` or `bool`: A string representing the remaining conditions from the marker, or `True` or `False` if the
                         marker can be evaluated completely
    """
    if marker is None:
        return True

    if isinstance(marker, Marker):
        marker = marker._markers

    if type(marker) is str and marker in {'or', 'and'}:
        return marker

    elif type(marker) is bool:
        return marker

    elif type(marker) is tuple:
        env = marker[0].value
        if env not in environments:
            return _single_marker_to_rpm_condition(marker, templates)
        evaluator = Marker(f'{marker[0].value} {marker[1].value} "{marker[2].value}"')
        if type(environments[env]) is list:
            evaluations = [evaluator.evaluate({env: val}) for val in environments[env]]
        else:
            evaluations = [evaluator.evaluate(environments)]
        return (True if all(evaluations) else False if all(not(ev) for ev in evaluations) else True if env == 'extras'
                else _single_marker_to_rpm_condition(marker, templates))

    elif type(marker) is list:
        simple_markers = [simplify_marker_to_rpm_condition(mk, environments, templates) for mk in marker]
        # disjunctive normal form: drop nested `True`s, `False`s, promote single-item lists and interpret empty lists
        splits = [n for n, v in enumerate(marker) if v == 'or']
        dnf = [[mk for mk in simple_markers[slice(before + 1, last)] if mk != 'and' and mk is not True]
               for before, last in zip([-1, *splits], [*splits, None])]
        dnf = [True if not cl else cl[0] if len(cl) == 1 else cl for cl in dnf if not any(ev is False for ev in cl)]
        return (False if not dnf else True if any(cl is True for cl in dnf)
                else ' and '.join(dnf[0]) if len(dnf) == 1
                else '(' + ' or '.join(' and '.join(mk) if type(mk) is list else mk for mk in dnf) + ')')


def specifier_to_rpm_version(package, version):
    """ Compute the version-specified dependency of a package to a RPM version requirement

    Args:
        package (`str`): A string that is the python package on which to depend
        version (:class:`~packaging.specifiers.SpecifierSet`): the version specifications

    Returns:
        `str`: A string representing the package dependency with versions
    """
    rpm_specs = []
    for spec in version:
        version = spec.version.rstrip(".*")
        rpm_op = _rpm_operator_correspondance.get(spec.operator)
        if rpm_op is not None:
            rpm_specs.append(f'{package} {rpm_op} {version}')
        elif spec.operator == '~=':
            # Caret forces higher sorting (tilde lower)
            rpm_specs.extend([f'{package} >= {version}', f'{package} < {version}^zzz'])
        elif spec.operator == '!=':
            rpm_specs.append(f'({package} < {version} or {package} > {version})')

    if rpm_specs:
        return ', '.join(rpm_specs)

    return package
