"""Run through `docker-compose run -T odoo odoo shell` after module install."""
import os

admin = env.ref("base.user_admin")
admin.write({"password": os.environ["ODOO_LOGIN_PASSWORD"]})
env.cr.commit()
print("ODOO_ADMIN_PASSWORD_SET")
