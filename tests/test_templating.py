import pathlib
import pysrpm.rpm


package_root = pathlib.Path(__file__).parent / 'setupcfg_package'

def get_rpm_instance(source=package_root, **options):
    return pysrpm.rpm.RPM(source, **options)

def get_metadata(with_deps=False, **options):
    with get_rpm_instance(**options) as rpm:
        rpm.load_configuration()
        return rpm.load_source_metadata(rpm.root, with_deps)

def get_specfile(tag=None, **options):
    with get_rpm_instance(**options) as rpm:
        rpm.load_configuration()
        pkg_info = rpm.load_source_metadata(rpm.root, False)

        spec = rpm.make_spec(pkg_info)
        if tag:
            return [line.split(':', 1)[1].strip() for line in spec.split('\n') if line.startswith(f'{tag}: ')]
        else:
            return spec


def test_template_specialisation():
    # Default
    assert get_specfile('BuildRequires') == ['findutils python3-devel', 'python%{python3_version}dist(setuptools) >= 40.8.0, python%{python3_version}dist(wheel)']
    assert get_specfile('Provides') == ['python%{python3_version}dist(package)']

    # CLI / kwargs override
    assert get_specfile('BuildRequires', python_package='python-{name}') == ['findutils python3-devel', 'python-setuptools >= 40.8.0, python-wheel']
    assert get_specfile('Provides', python_package='python-{name}') == ['python-package']

    # Try from a config file with an inherited flavour
    cfg = pathlib.Path('test.config')
    with open(cfg, 'w') as f:
        print('[pysrpm]\nflavour=test\n[test]\npython_package=python-{name}', file=f)

    try:
        assert get_specfile('BuildRequires', config=cfg) == ['findutils python3-devel', 'python-setuptools >= 40.8.0, python-wheel']
        assert get_specfile('Provides', config=cfg) == ['python-package']
    finally:
        cfg.unlink()

    # Add pysrpm. to config section
    with open(cfg, 'w') as f:
        print('[pysrpm]\nflavour=test\n[pysrpm.test]\npython_package=python-{name}', file=f)

    try:
        assert get_specfile('BuildRequires', config=cfg) == ['findutils python3-devel', 'python-setuptools >= 40.8.0, python-wheel']
        assert get_specfile('Provides', config=cfg) == ['python-package']
    finally:
        cfg.unlink()

    # Try from a TOML config file
    cfg = pathlib.Path('test.toml')
    with open(cfg, 'w') as f:
        print('''[tool.pysrpm]\nflavour = 'test'\n[tool.pysrpm.test]\npython_package = "python-{name}"''', file=f)
    try:
        assert get_specfile('BuildRequires', config=cfg) == ['findutils python3-devel', 'python-setuptools >= 40.8.0, python-wheel']
        assert get_specfile('Provides', config=cfg) == ['python-package']
    finally:
        cfg.unlink()
