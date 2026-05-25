"""Setup file for ur_kinematics_node package."""

import os
from glob import glob
from setuptools import setup, find_packages

package_name = 'ur_kinematics_node'

setup(
    name=package_name,
    version='1.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/config', glob('config/*.rviz')),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Kevin Medrano',
    maintainer_email='kmedrano@example.com',
    description='ROS2 kinematics node for Universal Robots using screw theory',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'kinematics_server = ur_kinematics_node.kinematics_server:main',
            'target_follower = ur_kinematics_node.target_follower:main',
        ],
    },
)
