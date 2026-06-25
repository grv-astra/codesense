class UsersController < ApplicationController
  def index
    # safe: parameterized bind, user input is not interpolated into SQL
    @users = User.where("name = ?", params[:name])
  end
end
