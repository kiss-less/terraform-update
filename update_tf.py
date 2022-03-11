import os
import sys
from pathlib import Path

TARGET_TF_VERSION = "latest:^1.1"
ERRORS_LIST = []

# Helper methods

def check_env_vars():
    env_vars_list = ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"]
    for var in env_vars_list:
        if os.environ[var] == None:
            print("Please set the {} env var".format(var))
            sys.exit(1)

def get_list_of_dirs():
    rootdir = '.'
    list = []
    for file in os.listdir():
        if os.path.isdir(file):
            list.append(file)
    print("List of dirs: {}".format(list))
    return list

def check_if_file_exists(filename):
    if Path(filename).exists():
        return True
    else:
        return False

def check_if_new_tf_file_version_is_target(dir):
    print("Checking TF version")
    ver_filename = "{}/.terraform-version".format(dir)
    if check_if_file_exists(ver_filename):
        with open(ver_filename) as ver_file:
            for line in ver_file:
                if TARGET_TF_VERSION in line:
                    print("TF version is the same as the target one")
                    return True
    print("TF version is not the same as the target one")
    return False

def update_tf_version_to_target(dir):
    print("Updating TF version to {}".format(TARGET_TF_VERSION))
    ver_filename = "{}/.terraform-version".format(dir)
    with open(ver_filename, "w") as ver_file:
        ver_file.truncate(0)
        ver_file.write(TARGET_TF_VERSION)

def delete_old_versions_file(dir):
    ver_filename = "{}/versions.tf".format(dir)
    print("Checking if the old {} file exists".format(ver_filename))
    if check_if_file_exists(ver_filename):
        print("Removing the old {} file".format(ver_filename))
        os.remove(ver_filename)
    else:
        print("There is no {}".format(ver_filename))

def run_tf(dir):
    print("Running terraform init. It is ok if it fails due to the version issues, but it is required to prepare for the version update.")
    os.system("cd {} && terraform init".format(dir))
    print("Running terraform state replace-provider for aws provider")
    replace_result = os.system("cd {} && terraform state replace-provider -auto-approve registry.terraform.io/-/aws hashicorp/aws".format(dir))
    if replace_result != 0:
        ERRORS_LIST.append("Folder {}. Terraform state replace-provider exit code: {}".format(dir, replace_result))
    print("Running terraform init again to make sure changes were applied")
    init_result = os.system("cd {} && terraform init".format(dir))
    if init_result != 0:
        ERRORS_LIST.append("Folder {}. Terraform init exit code: {}".format(dir, init_result))

# Execution

check_env_vars()
dirs_list = get_list_of_dirs()

for dir in dirs_list:
    print("Running in {}".format(dir))
    if not check_if_new_tf_file_version_is_target(dir):
        update_tf_version_to_target(dir)
        delete_old_versions_file(dir)
        run_tf(dir)
    else:
        print("TF version update for {} is not required".format(dir))

if not ERRORS_LIST:
    print("The update has been successfully finished. Please double-check if all the required files were created and commit changes to Version Control")
else:
    print("Something went wrong during the update. Please check the errors below:")
    for error in ERRORS_LIST:
        print(error)
    print("Please check the modules manually")
