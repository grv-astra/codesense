class UsersController < ApplicationController
  def index
    # SQLi: interpolated user input in a where clause
    @users = User.where("name = '#{params[:name]}'")
  end
end
