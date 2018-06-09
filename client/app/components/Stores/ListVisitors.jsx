import React from 'react';
import {Col, Row, Panel, Alert} from 'react-bootstrap';
import {withRouter, Link} from "react-router-dom";
import {Stomp} from 'stompjs/lib/stomp.min';
import axios from "axios/index";
import VisitSummary from './VisitSummary';

class ListVisitors extends React.Component {
    constructor(props) {
        super(props);

        this.state = {};
    }

    /**
     * This function is used to load the relist of visitors
     */
    reloadVisitorList()
    {
        axios({
            method: 'get',
            url: `/store/${this.props.store._id}/visitors/`
        }).then((response) =>
        {
            const state = this.state;
            state.visitors = response.data;
            if (this.props.match && this.props.match.params && this.props.match.params.visitorId)
            {
                axios({
                    method: 'get',
                    url: `/store/${this.props.store._id}/visitors/${this.props.match.params.visitorId}`
                }).then((response) => {
                    state.visitor = response.data;
                    this.setState(state);
                });
            }
            else
            {
                this.setState(state);
            }
        });
    }

    /**
     * Triggered when this component appears on the screen.
     */
    componentDidMount() {
        if (!this.state.visitors)
        {
            this.reloadVisitorList();
        }

        this.updateInterval = setInterval(() => this.reloadVisitorList(), 2500);
    }


    /**
     * Triggered when this component is being removed from the screen
     */
    componentWillUnmount()
    {
        if (this.updateInterval)
        {
            clearInterval(this.updateInterval);
        }
    }

    render() {
        return (
            <div className="store-cameras">
                <br/>
                <Row>
                    <Col md={3}>
                        <div className="panel b">
                            <div className="panel-body">
                                <strong className="text-muted">Recent Visitors</strong>
                            </div>
                            <div className="list-group">
                                {
                                    this.state.visitors &&
                                    this.state.visitors.map((visitor) =>
                                        <Link key={visitor.visitorId} to={"/store/" + this.props.store._id + "/visitor/" + visitor.visitorId}
                                              className={"list-group-item " + (this.state.visitor && visitor.visitorId === this.state.visitor.visitorId ? " active" : "")}>
                                            <span>{visitor.visitorId}</span>
                                        </Link>
                                    )
                                }
                            </div>
                        </div>
                    </Col>
                    {this.state.visitor &&
                        <VisitSummary visitor={this.state.visitor} store={this.props.store}/>
                    }
                </Row>
            </div>
        );
    }
}

export default withRouter(ListVisitors);


