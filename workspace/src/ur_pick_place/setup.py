import os
from glob import glob
from setuptools import setup, find_packages

package_name = 'ur_pick_place'

setup(
    name=package_name,
    version='1.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/config', glob('config/*.yaml')),
        ('share/' + package_name + '/config', glob('config/*.rviz')),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
        ('share/' + package_name + '/urdf', glob('urdf/*.xacro')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Kevin Medrano',
    maintainer_email='kmedrano@example.com',
    description='Pick and place package for UR robots with simulated gripper on industrial table',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'pick_place_node = ur_pick_place.pick_place_node:main',
            'gripper_controller = ur_pick_place.gripper_controller:main',
        ],
    },
)
