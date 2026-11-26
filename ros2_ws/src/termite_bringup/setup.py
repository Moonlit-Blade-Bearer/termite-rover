from glob import glob

from setuptools import setup

package_name = 'termite_bringup'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
        ('share/' + package_name + '/config', glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='chl',
    maintainer_email='chl@localhost',
    description='白蚁探测无人车统一启动包',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'static_tf_pub = termite_bringup.static_tf:main',
            'linux_joy = termite_bringup.linux_joy:main',
            'joy_teleop = termite_bringup.joy_teleop:main',
            'vision_receiver = termite_bringup.vision_receiver:main',
            'termite_detector = termite_bringup.termite_detector:main',
        ],
    },
)
