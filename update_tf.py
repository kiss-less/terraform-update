import os
import subprocess
import sys
from pathlib import Path

TARGET_TF_VERSION = "latest:^1.1"
TARGET_AWS_PROVIDER_VERSION = ">=4.0"
AWS_PROVIDER_VERSION_CONSTRAINT = "<4.0" # This constraint will be applied to the versions.tf file if there are "Value for unconfigurable attribute" errors in the stderr of the terraform plan
ERRORS_LIST = []


# Helper methods

def check_env_vars():
    env_vars_list = ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"]
    for var in env_vars_list:
        if os.environ.get(var) is None:
            print("Please set the {} env var before execution!".format(var))
            sys.exit(1)

def get_list_of_dirs():
    rootdir = '.'
    list = []
    for file in os.listdir():
        if os.path.isdir(file):
            list.append(file)
    list.sort()
    print("List of dirs: {}".format(list))
    return list

def check_if_file_exists(filename):
    if Path(filename).exists():
        return True
    else:
        return False

def check_if_hcl_lock_file_exists(dir):
    print("Checking if hcl lock file exists")
    lock_filename = "{}/.terraform.lock.hcl".format(dir)
    if check_if_file_exists(lock_filename):
        print("The lock file exists for the {} module".format(dir))
        return True
    else:
        print("The lock file doesn't exist for the {} module".format(dir))
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

def adjust_old_versions_file(dir):
    with open ("{}/versions.tf".format(dir), "w") as old_ver_file:
        old_ver_file.truncate(0)
        old_ver_file.write(f"""
terraform {{
  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "{TARGET_AWS_PROVIDER_VERSION}"
    }}
  }}
}}
""")

def run_tf(dir):
    print("Running terraform init. It is ok if it fails due to the version issues, but it is required to prepare for the version update.")
    os.system("cd {} && terraform init -upgrade".format(dir))
    print("Running terraform state replace-provider")
    providers = ["aws", "template", "null"]
    for provider in providers:
        replace_result = os.system("cd {} && terraform state replace-provider -auto-approve registry.terraform.io/-/{} hashicorp/{}".format(dir, provider, provider))
        if replace_result != 0:
            ERRORS_LIST.append("Folder {}. Terraform state replace-provider exit code: {}".format(dir, replace_result))
    print("Running terraform init again to make sure changes were applied")
    init_plan_result = os.system("cd {} && terraform init -upgrade && terraform plan".format(dir))
    if init_plan_result != 0:
        s3_check = subprocess.Popen(['terraform', 'plan'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=dir)
        if "Value for unconfigurable attribute" in str(s3_check.communicate()[1]):
            add_version_constraint(dir)
        elif s3_check.returncode != 0:
            ERRORS_LIST.append("Folder {}. Terraform init and plan exit code: {}".format(dir, s3_check.returncode))
    else:
        os.remove("{}/versions.tf".format(dir))
    run_tf_fmt(dir)

def run_tf_init_upgrade_and_plan(dir):
    print("Running terraform init upgrade and plan")
    upgrade_and_plan_result = os.system("cd {} && terraform init -upgrade && terraform plan".format(dir))
    if upgrade_and_plan_result != 0:
        ERRORS_LIST.append("Folder {}. Terraform init upgrade and plan exit code: {}".format(dir, upgrade_and_plan_result))

def add_version_constraint(dir):
    with open ("{}/versions.tf".format(dir), "w") as old_ver_file:
        old_ver_file.truncate(0)
        old_ver_file.write(f"""
terraform {{
  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "{AWS_PROVIDER_VERSION_CONSTRAINT}"
    }}
  }}
}}
""")
    run_tf_init_upgrade_and_plan(dir)

def run_tf_plan(dir):
    tf_plan_result = os.system("cd {} && terraform plan".format(dir))
    if tf_plan_result != 0:
        ERRORS_LIST.append("Folder {}. Terraform plan exit code: {}".format(dir, tf_plan_result))

def run_tf_fmt(dir):
    tf_fmt_result = os.system("cd {} && terraform fmt".format(dir))
    if tf_fmt_result != 0:
        ERRORS_LIST.append("Folder {}. Terraform fmt exit code: {}".format(dir, tf_fmt_result))


# Execution

check_env_vars()
dirs_list = get_list_of_dirs()

for dir in dirs_list:
    # Uncomment the next line if you need to check if the configuration is correct for all the dirs. Comment the rest of the lines if they are not required
    # run_tf_plan(dir)

    # Uncomment the next line if you need to update the lock file constrains\versions. Comment the rest of the lines if they are not required
    # run_tf_init_upgrade_and_plan(dir)

    # Main execution chain
    print("Running in {}".format(dir))
    if (not check_if_new_tf_file_version_is_target(dir) or not check_if_hcl_lock_file_exists(dir)):
        update_tf_version_to_target(dir)
        adjust_old_versions_file(dir)
        run_tf(dir)
    else:
        print("TF version update for {} is not required".format(dir))

# Uncomment the next line if you need to add aws provider version constraint to some module. Comment the rest of the lines if they are not required
# add_version_constraint("assets")

if not ERRORS_LIST:
    print("The update has been successfully finished. Please double-check if all the required files were created and commit changes to Version Control")
else:
    print("Something went wrong during the update. Please check the errors below:")
    for error in ERRORS_LIST:
        print(error)
    print("Please check the modules manually")
