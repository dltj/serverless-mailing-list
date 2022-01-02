""" Lambda handler for the homepage """

import json
from utilities.log_config import logger
from utilities.jinja_renderer import site_wrap


SIGNUP_FORM = """
      <form class="form-horizontal" method="post" action="/subscribe">
        <div class="form-group">
          <label for="inputEmail3" class="col-sm-2 control-label">Email</label>
          <div class="col-sm-10">
            <input type="email" class="form-control" id="email" name="email" placeholder="Email">
          </div>
        </div>
        <div class="form-group">
          <div class="col-sm-offset-2 col-sm-10">
            <button type="submit" class="btn btn-success">Sign Up</button>
          </div>
        </div>
      </form>
"""


def endpoint(event, context):
    logger.info(json.dumps(event))
    response = site_wrap(title="Newsletter Signup", content=SIGNUP_FORM)
    return response
